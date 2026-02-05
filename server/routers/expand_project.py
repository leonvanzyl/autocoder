"""
Expand Project Router
=====================

WebSocket and REST endpoints for interactive project expansion with Claude.
Allows adding multiple features to existing projects via natural language.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from ..schemas import ImageAttachment
from ..services.expand_chat_session import (
    ExpandChatSession,
    create_expand_session,
    get_expand_session,
    list_expand_sessions,
    remove_expand_session,
)
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expand", tags=["expand-project"])



# ============================================================================
# REST Endpoints
# ============================================================================

class ExpandSessionStatus(BaseModel):
    """Status of an expansion session."""
    project_name: str
    is_active: bool
    is_complete: bool
    features_created: int
    message_count: int


@router.get("/sessions", response_model=list[str])
async def list_expand_sessions_endpoint():
    """List all active expansion sessions."""
    return list_expand_sessions()


@router.get("/sessions/{project_name}", response_model=ExpandSessionStatus)
async def get_expand_session_status(project_name: str):
    """Get status of an expansion session."""
    project_name = validate_project_name(project_name)

    session = get_expand_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active expansion session for this project")

    return ExpandSessionStatus(
        project_name=project_name,
        is_active=True,
        is_complete=session.is_complete(),
        features_created=session.get_features_created(),
        message_count=len(session.get_messages()),
    )


@router.delete("/sessions/{project_name}")
async def cancel_expand_session(project_name: str):
    """Cancel and remove an expansion session."""
    project_name = validate_project_name(project_name)

    session = get_expand_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active expansion session for this project")

    await remove_expand_session(project_name)
    return {"success": True, "message": "Expansion session cancelled"}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{project_name}")
async def expand_project_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for interactive project expansion chat.

    Message protocol:

    Client -> Server:
    - {"type": "start"} - Start the expansion session
    - {"type": "message", "content": "..."} - Send user message
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "text", "content": "..."} - Text chunk from Claude
    - {"type": "features_created", "count": N, "features": [...]} - Features added
    - {"type": "expansion_complete", "total_added": N} - Session complete
    - {"type": "response_done"} - Response complete
    - {"type": "error", "content": "..."} - Error message
    - {"type": "pong"} - Keep-alive pong
    """
    # Always accept the WebSocket first to avoid opaque 403 errors.
    # Starlette returns 403 if we close before accepting.
    await websocket.accept()

    try:
        project_name = validate_project_name(project_name)
    except HTTPException:
        await websocket.send_json({"type": "error", "content": "Invalid project name"})
        await websocket.close(code=4000, reason="Invalid project name")
        return

    # Look up project directory from registry
    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.send_json({"type": "error", "content": "Project not found in registry"})
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.send_json({"type": "error", "content": "Project directory not found"})
        await websocket.close(code=4004, reason="Project directory not found")
        return

    # Verify project has app_spec.txt
    from autoforge_paths import get_prompts_dir
    spec_path = get_prompts_dir(project_dir) / "app_spec.txt"
    if not spec_path.exists():
        await websocket.send_json({"type": "error", "content": "Project has no spec. Create a spec first before expanding."})
        await websocket.close(code=4004, reason="Project has no spec. Create spec first.")
        return

    session: Optional[ExpandChatSession] = None

    try:
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                elif msg_type == "start":
                    # Check if session already exists (idempotent start)
                    existing_session = get_expand_session(project_name)
                    if existing_session:
                        session = existing_session
                        await websocket.send_json({
                            "type": "text",
                            "content": "Resuming existing expansion session. What would you like to add?"
                        })
                        await websocket.send_json({"type": "response_done"})
                    else:
                        # Create and start a new expansion session
                        session = await create_expand_session(project_name, project_dir)

                        # Stream the initial greeting
                        async for chunk in session.start():
                            await websocket.send_json(chunk)

                elif msg_type == "message":
                    # User sent a message
                    if not session:
                        session = get_expand_session(project_name)
                        if not session:
                            await websocket.send_json({
                                "type": "error",
                                "content": "No active session. Send 'start' first."
                            })
                            continue

                    user_content = message.get("content", "").strip()

                    # Parse attachments if present
                    attachments: list[ImageAttachment] = []
                    raw_attachments = message.get("attachments", [])
                    if raw_attachments:
                        try:
                            for raw_att in raw_attachments:
                                attachments.append(ImageAttachment(**raw_att))
                        except (ValidationError, Exception) as e:
                            logger.warning(f"Invalid attachment data: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "content": "Invalid attachment format"
                            })
                            continue

                    # Allow empty content if attachments are present
                    if not user_content and not attachments:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Empty message"
                        })
                        continue

                    # Stream Claude's response
                    async for chunk in session.send_message(user_content, attachments if attachments else None):
                        await websocket.send_json(chunk)

                elif msg_type == "done":
                    # User is done adding features
                    if session:
                        await websocket.send_json({
                            "type": "expansion_complete",
                            "total_added": session.get_features_created()
                        })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Unknown message type: {msg_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON"
                })

    except WebSocketDisconnect:
        logger.info(f"Expand chat WebSocket disconnected for {project_name}")

    except Exception:
        logger.exception(f"Expand chat WebSocket error for {project_name}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": "Internal server error"
            })
        except Exception:
            pass

    finally:
        # Don't remove the session on disconnect - allow resume
        pass
