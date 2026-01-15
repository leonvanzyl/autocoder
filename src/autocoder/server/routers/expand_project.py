"""
Expand Project Router
=====================

WebSocket + REST endpoints for interactive project expansion.

This chat reads the existing `prompts/app_spec.txt` and, when the assistant emits
`<features_to_create>[...]</features_to_create>`, creates those features in the
project's `agent_system.db`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expand", tags=["expand-project"])


def _get_project_path(project_name: str) -> Path:
    from autocoder.agent.registry import get_project_path

    p = get_project_path(project_name)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found in registry")
    return Path(p)


def validate_project_name(name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")
    return name


class ExpandSessionStatus(BaseModel):
    project_name: str
    is_active: bool
    features_created: int
    message_count: int


@router.get("/sessions", response_model=list[str])
async def list_expand_sessions_endpoint():
    return list_expand_sessions()


@router.get("/sessions/{project_name}", response_model=ExpandSessionStatus)
async def get_expand_session_status(project_name: str):
    project_name = validate_project_name(project_name)
    session = get_expand_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active expansion session for this project")

    return ExpandSessionStatus(
        project_name=project_name,
        is_active=True,
        features_created=session.get_features_created(),
        message_count=len(session.get_messages()),
    )


@router.delete("/sessions/{project_name}")
async def cancel_expand_session(project_name: str):
    project_name = validate_project_name(project_name)
    session = get_expand_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active expansion session for this project")
    await remove_expand_session(project_name)
    return {"success": True, "message": "Expansion session cancelled"}


@router.websocket("/ws/{project_name}")
async def expand_project_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for interactive project expansion chat.

    Client -> Server:
    - {"type": "start"} - Start/resume a session
    - {"type": "message", "content": "...", "attachments": [...]} - User message
    - {"type": "done"} - Mark expansion complete (UI convenience)
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "text", "content": "..."} - Streaming assistant text
    - {"type": "features_created", "count": N, "features": [...]} - Features created
    - {"type": "expansion_complete", "total_added": N} - Session complete
    - {"type": "response_done"} - Response complete
    - {"type": "error", "content": "..."} - Error message
    - {"type": "pong"} - Keep-alive pong
    """
    try:
        project_name = validate_project_name(project_name)
    except HTTPException:
        await websocket.close(code=4000, reason="Invalid project name")
        return

    project_dir = _get_project_path(project_name)
    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    spec_path = project_dir / "prompts" / "app_spec.txt"
    if not spec_path.exists():
        await websocket.close(code=4004, reason="Project has no spec. Create spec first.")
        return

    await websocket.accept()

    session: Optional[ExpandChatSession] = None

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if msg_type == "start":
                    existing = get_expand_session(project_name)
                    if existing:
                        session = existing
                        await websocket.send_json(
                            {
                                "type": "text",
                                "content": "Resuming expansion session. What would you like to add?",
                            }
                        )
                        await websocket.send_json({"type": "response_done"})
                        continue

                    session = await create_expand_session(project_name, project_dir)
                    async for chunk in session.start():
                        await websocket.send_json(chunk)
                    continue

                if msg_type == "done":
                    if session:
                        await websocket.send_json(
                            {"type": "expansion_complete", "total_added": session.get_features_created()}
                        )
                    continue

                if msg_type == "message":
                    if not session:
                        session = get_expand_session(project_name)
                        if not session:
                            await websocket.send_json(
                                {"type": "error", "content": "No active session. Send 'start' first."}
                            )
                            continue

                    user_content = str(message.get("content") or "").strip()

                    attachments: list[ImageAttachment] = []
                    raw_attachments = message.get("attachments", [])
                    if raw_attachments:
                        try:
                            for raw_att in raw_attachments:
                                attachments.append(ImageAttachment(**raw_att))
                        except (ValidationError, Exception) as e:
                            logger.warning(f"Invalid attachment data: {e}")
                            await websocket.send_json({"type": "error", "content": "Invalid attachment format"})
                            continue

                    if not user_content and not attachments:
                        await websocket.send_json({"type": "error", "content": "Empty message"})
                        continue

                    async for chunk in session.send_message(
                        user_content,
                        attachments if attachments else None,
                    ):
                        await websocket.send_json(chunk)
                    continue

                await websocket.send_json({"type": "error", "content": f"Unknown message type: {msg_type}"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info(f"Expand chat WebSocket disconnected for {project_name}")
    except Exception:
        logger.exception(f"Expand chat WebSocket error for {project_name}")
        try:
            await websocket.send_json({"type": "error", "content": "Internal server error"})
        except Exception:
            pass
    finally:
        # Keep session for resume; explicit delete via REST if needed.
        pass

