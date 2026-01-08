"""
Chat-to-Features Router
=======================

WebSocket endpoint for conversational feature creation.
Users describe features in natural language, Claude suggests structured features,
and users can accept/reject suggestions to create features in the database.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..validators import is_valid_project_name
from ..services.chat_to_features_session import (
    ChatToFeaturesSession,
    create_session,
    get_session,
    list_sessions,
    remove_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["chat-to-features"])

# Root directory
ROOT_DIR = Path(__file__).parent.parent.parent


def _get_project_path(project_name: str) -> Optional[Path]:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_db_classes():
    """Lazy import of database classes."""
    import sys
    from pathlib import Path
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from api.database import Feature, create_database
    return create_database, Feature


async def _create_feature_in_db(project_dir: Path, feature_data: dict) -> dict:
    """
    Create a feature in the database.

    Args:
        project_dir: Project directory path
        feature_data: Feature data with keys: name, category, description, steps

    Returns:
        Dict with feature_id and feature data
    """
    create_database, Feature = _get_db_classes()
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()

    try:
        # Get next priority
        max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
        priority = (max_priority.priority + 1) if max_priority else 1

        # Create new feature
        db_feature = Feature(
            priority=priority,
            category=feature_data["category"],
            name=feature_data["name"],
            description=feature_data["description"],
            steps=feature_data["steps"],
            passes=False,
            in_progress=False,
        )

        session.add(db_feature)
        session.commit()
        session.refresh(db_feature)

        return {
            "feature_id": db_feature.id,
            "feature": {
                "id": db_feature.id,
                "priority": db_feature.priority,
                "category": db_feature.category,
                "name": db_feature.name,
                "description": db_feature.description,
                "steps": db_feature.steps if isinstance(db_feature.steps, list) else [],
                "passes": db_feature.passes,
                "in_progress": db_feature.in_progress,
            }
        }
    finally:
        session.close()


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/{project_name}/chat")
async def chat_to_features_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for chat-to-features.

    Message protocol:

    Client -> Server:
    - {"type": "start"} - Start the chat session
    - {"type": "message", "content": "..."} - Send user message
    - {"type": "accept_feature", "feature_index": 0} - Accept a feature suggestion
    - {"type": "reject_feature", "feature_index": 0} - Reject a feature suggestion
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "text", "content": "..."} - Text chunk from Claude
    - {"type": "feature_suggestion", "index": 0, "feature": {...}} - Feature suggestion
    - {"type": "feature_created", "feature_id": 123, "feature": {...}} - Feature created
    - {"type": "response_done"} - Response complete
    - {"type": "error", "content": "..."} - Error message
    - {"type": "pong"} - Keep-alive pong
    """
    if not is_valid_project_name(project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    await websocket.accept()
    logger.info(f"Chat-to-features WebSocket connected for project: {project_name}")

    session: Optional[ChatToFeaturesSession] = None

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")
                logger.info(f"Chat-to-features received message type: {msg_type}")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                elif msg_type == "start":
                    # Create a new session
                    try:
                        session = await create_session(project_name, project_dir)

                        # Stream the initial greeting
                        async for chunk in session.start():
                            await websocket.send_json(chunk)
                    except Exception as e:
                        logger.exception(f"Error starting chat-to-features session for {project_name}")
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Failed to start session: {str(e)}"
                        })

                elif msg_type == "message":
                    if not session:
                        session = get_session(project_name)
                        if not session:
                            await websocket.send_json({
                                "type": "error",
                                "content": "No active session. Send 'start' first."
                            })
                            continue

                    user_content = message.get("content", "").strip()
                    if not user_content:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Empty message"
                        })
                        continue

                    # Stream Claude's response
                    async for chunk in session.send_message(user_content):
                        await websocket.send_json(chunk)

                elif msg_type == "accept_feature":
                    if not session:
                        session = get_session(project_name)
                        if not session:
                            await websocket.send_json({
                                "type": "error",
                                "content": "No active session"
                            })
                            continue

                    feature_index = message.get("feature_index")
                    if feature_index is None:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Missing feature_index"
                        })
                        continue

                    try:
                        # Get the feature suggestion from the session
                        feature_data = session.get_feature_suggestion(feature_index)
                        if not feature_data:
                            await websocket.send_json({
                                "type": "error",
                                "content": f"Feature suggestion {feature_index} not found"
                            })
                            continue

                        # Create the feature in the database
                        result = await _create_feature_in_db(project_dir, feature_data)

                        # Remove the suggestion from the session (mark as accepted)
                        session.remove_feature_suggestion(feature_index, status="accepted")

                        # Send success response (include feature_index for client-side removal)
                        await websocket.send_json({
                            "type": "feature_created",
                            "feature_index": feature_index,
                            "feature_id": result["feature_id"],
                            "feature": result["feature"]
                        })

                    except Exception as e:
                        logger.exception(f"Error creating feature from suggestion {feature_index}")
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Failed to create feature: {str(e)}"
                        })

                elif msg_type == "reject_feature":
                    if not session:
                        session = get_session(project_name)
                        if not session:
                            await websocket.send_json({
                                "type": "error",
                                "content": "No active session"
                            })
                            continue

                    feature_index = message.get("feature_index")
                    if feature_index is None:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Missing feature_index"
                        })
                        continue

                    # Remove the suggestion from the session
                    session.remove_feature_suggestion(feature_index)

                    # Send acknowledgment (optional, could be silent)
                    await websocket.send_json({
                        "type": "feature_rejected",
                        "feature_index": feature_index
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
        logger.info(f"Chat-to-features WebSocket disconnected for {project_name}")

    except Exception as e:
        logger.exception(f"Chat-to-features WebSocket error for {project_name}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Server error: {str(e)}"
            })
        except Exception:
            pass

    finally:
        # Don't remove session on disconnect - allow resume
        pass


# ============================================================================
# REST Endpoints - Session Management (Optional)
# ============================================================================

@router.get("/{project_name}/chat/sessions")
async def list_chat_sessions(project_name: str):
    """List active chat-to-features sessions for this project."""
    all_sessions = list_sessions()
    # Filter to only include sessions matching this project
    project_sessions = [s for s in all_sessions if s == project_name]
    return {"sessions": project_sessions}


@router.delete("/{project_name}/chat/sessions")
async def close_chat_session(project_name: str):
    """Close an active chat-to-features session."""
    if not is_valid_project_name(project_name):
        return {"success": False, "message": "Invalid project name"}

    session = get_session(project_name)
    if not session:
        return {"success": False, "message": "No active session for this project"}

    await remove_session(project_name)
    return {"success": True, "message": "Session closed"}
