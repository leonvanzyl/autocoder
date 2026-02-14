"""
Expand Chat Session
===================

Manages interactive project expansion conversation with Claude.
Uses the expand-project.md skill to help users add features to existing projects.
"""

import asyncio
import json
import logging
import shutil
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from dotenv import load_dotenv

from ..schemas import ImageAttachment
from .chat_constants import ROOT_DIR, make_multimodal_message

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Feature MCP tools needed for expand session
EXPAND_FEATURE_TOOLS = [
    "mcp__features__feature_create",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_get_stats",
]


class ExpandChatSession:
    """
    Manages a project expansion conversation.

    Unlike SpecChatSession which writes spec files, this session:
    1. Reads existing app_spec.txt for context
    2. Chats with the user to define new features
    3. Claude creates features via the feature_create_bulk MCP tool
    """

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the session.

        Args:
            project_name: Name of the project being expanded
            project_dir: Absolute path to the project directory
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.client: Optional[ClaudeSDKClient] = None
        self.messages: list[dict] = []
        self.complete: bool = False
        self.created_at = datetime.now()
        self._conversation_id: Optional[str] = None
        self._client_entered: bool = False
        self.features_created: int = 0
        self.created_feature_ids: list[int] = []
        self._settings_file: Optional[Path] = None
        self._query_lock = asyncio.Lock()

    async def close(self) -> None:
        """Clean up resources and close the Claude client."""
        if self.client and self._client_entered:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Claude client: {e}")
            finally:
                self._client_entered = False
                self.client = None

        # Clean up temporary settings file
        if self._settings_file and self._settings_file.exists():
            try:
                self._settings_file.unlink()
            except Exception as e:
                logger.warning(f"Error removing settings file: {e}")

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session and get initial greeting from Claude.

        Yields message chunks as they stream in.
        """
        # Load the expand-project skill
        skill_path = ROOT_DIR / ".claude" / "commands" / "expand-project.md"

        if not skill_path.exists():
            yield {
                "type": "error",
                "content": f"Expand project skill not found at {skill_path}"
            }
            return

        # Verify project has existing spec
        from autoforge_paths import get_prompts_dir
        spec_path = get_prompts_dir(self.project_dir) / "app_spec.txt"
        if not spec_path.exists():
            yield {
                "type": "error",
                "content": "Project has no app_spec.txt. Please create it first using spec creation."
            }
            return

        try:
            skill_content = skill_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skill_content = skill_path.read_text(encoding="utf-8", errors="replace")

        # Find and validate Claude CLI before creating temp files
        system_cli = shutil.which("claude")
        if not system_cli:
            yield {
                "type": "error",
                "content": "Claude CLI not found. Please install it: npm install -g @anthropic-ai/claude-code"
            }
            return

        # Create temporary security settings file (unique per session to avoid conflicts)
        # Note: permission_mode="bypassPermissions" is safe here because:
        # 1. Only Read/Glob file tools are allowed (no Write/Edit)
        # 2. MCP tools are restricted to feature creation only
        # 3. No Bash access - cannot execute arbitrary commands
        security_settings = {
            "sandbox": {"enabled": True},
            "permissions": {
                "defaultMode": "bypassPermissions",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                    *EXPAND_FEATURE_TOOLS,
                ],
            },
        }
        from autoforge_paths import get_expand_settings_path
        settings_file = get_expand_settings_path(self.project_dir, uuid.uuid4().hex)
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file = settings_file
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(security_settings, f, indent=2)

        # Replace $ARGUMENTS with absolute project path
        project_path = str(self.project_dir.resolve())
        system_prompt = skill_content.replace("$ARGUMENTS", project_path)

        # Build environment overrides for API configuration
        from registry import get_effective_sdk_env, get_model_for_role
        sdk_env = get_effective_sdk_env()

        # Determine model using per-role resolution (expand -> high tier)
        model = get_model_for_role("expand")

        # Build MCP servers config for feature creation
        mcp_servers = {
            "features": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.feature_mcp"],
                "env": {
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
        }

        # Create Claude SDK client
        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model=model,
                    cli_path=system_cli,
                    system_prompt=system_prompt,
                    allowed_tools=[
                        "Read",
                        "Glob",
                        "Grep",
                        "WebFetch",
                        "WebSearch",
                        *EXPAND_FEATURE_TOOLS,
                    ],
                    mcp_servers=mcp_servers,  # type: ignore[arg-type]  # SDK accepts dict config at runtime
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                    env=sdk_env,
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception:
            logger.exception("Failed to create Claude client")
            yield {
                "type": "error",
                "content": "Failed to initialize Claude"
            }
            return

        # Start the conversation
        try:
            async with self._query_lock:
                async for chunk in self._query_claude("Begin the project expansion process."):
                    yield chunk
            yield {"type": "response_done"}
        except Exception:
            logger.exception("Failed to start expand chat")
            yield {
                "type": "error",
                "content": "Failed to start conversation"
            }

    async def send_message(
        self,
        user_message: str,
        attachments: list[ImageAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Args:
            user_message: The user's response
            attachments: Optional list of image attachments

        Yields:
            Message chunks of various types:
            - {"type": "text", "content": str}
            - {"type": "features_created", "count": N, "features": [...]}
            - {"type": "expansion_complete", "total_added": N}
            - {"type": "error", "content": str}
        """
        if not self.client:
            yield {
                "type": "error",
                "content": "Session not initialized. Call start() first."
            }
            return

        # Store the user message
        self.messages.append({
            "role": "user",
            "content": user_message,
            "has_attachments": bool(attachments),
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Use lock to prevent concurrent queries from corrupting the response stream
            async with self._query_lock:
                async for chunk in self._query_claude(user_message, attachments):
                    yield chunk
            yield {"type": "response_done"}
        except Exception:
            logger.exception("Error during Claude query")
            yield {
                "type": "error",
                "content": "Error while processing message"
            }

    async def _query_claude(
        self,
        message: str,
        attachments: list[ImageAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Feature creation is handled by Claude calling the feature_create_bulk
        MCP tool directly -- no text parsing needed.
        """
        if not self.client:
            return

        # Build the message content
        if attachments and len(attachments) > 0:
            content_blocks: list[dict[str, Any]] = []
            if message:
                content_blocks.append({"type": "text", "text": message})
            for att in attachments:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att.mimeType,
                        "data": att.base64Data,
                    }
                })
            await self.client.query(make_multimodal_message(content_blocks))
            logger.info(f"Sent multimodal message with {len(attachments)} image(s)")
        else:
            await self.client.query(message)

        # Stream the response
        async for msg in self.client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        text = block.text
                        if text:
                            yield {"type": "text", "content": text}

                            self.messages.append({
                                "role": "assistant",
                                "content": text,
                                "timestamp": datetime.now().isoformat()
                            })

    def get_features_created(self) -> int:
        """Get the total number of features created in this session."""
        return self.features_created

    def is_complete(self) -> bool:
        """Check if expansion session is complete."""
        return self.complete

    def get_messages(self) -> list[dict]:
        """Get all messages in the conversation."""
        return self.messages.copy()


# Session registry with thread safety
_expand_sessions: dict[str, ExpandChatSession] = {}
_expand_sessions_lock = threading.Lock()


def get_expand_session(project_name: str) -> Optional[ExpandChatSession]:
    """Get an existing expansion session for a project."""
    with _expand_sessions_lock:
        return _expand_sessions.get(project_name)


async def create_expand_session(project_name: str, project_dir: Path) -> ExpandChatSession:
    """Create a new expansion session for a project, closing any existing one."""
    old_session: Optional[ExpandChatSession] = None

    with _expand_sessions_lock:
        old_session = _expand_sessions.pop(project_name, None)
        session = ExpandChatSession(project_name, project_dir)
        _expand_sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old expand session for {project_name}: {e}")

    return session


async def remove_expand_session(project_name: str) -> None:
    """Remove and close an expansion session."""
    session: Optional[ExpandChatSession] = None

    with _expand_sessions_lock:
        session = _expand_sessions.pop(project_name, None)

    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session for {project_name}: {e}")


def list_expand_sessions() -> list[str]:
    """List all active expansion session project names."""
    with _expand_sessions_lock:
        return list(_expand_sessions.keys())


async def cleanup_all_expand_sessions() -> None:
    """Close all active expansion sessions. Called on server shutdown."""
    sessions_to_close: list[ExpandChatSession] = []

    with _expand_sessions_lock:
        sessions_to_close = list(_expand_sessions.values())
        _expand_sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session {session.project_name}: {e}")
