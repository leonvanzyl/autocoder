"""
Spec Creation Chat Session
==========================

Manages interactive spec creation conversation with Claude.
Uses the create-spec.md skill to guide users through app spec creation.
"""

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv

from sdk_adapter import AdapterOptions, EventType, SDKAdapter, create_adapter

from ..schemas import ImageAttachment
from .chat_constants import ROOT_DIR

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)


class SpecChatSession:
    """
    Manages a spec creation conversation for one project.

    Uses the create-spec skill to guide users through:
    - Phase 1: Project Overview (name, description, audience)
    - Phase 2: Involvement Level (Quick vs Detailed mode)
    - Phase 3: Technology Preferences
    - Phase 4: Features (main exploration phase)
    - Phase 5: Technical Details (derived or discussed)
    - Phase 6-7: Success Criteria & Approval
    """

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the session.

        Args:
            project_name: Name of the project being created
            project_dir: Absolute path to the project directory
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.adapter: Optional[SDKAdapter] = None
        self.messages: list[dict] = []
        self.complete: bool = False
        self.created_at = datetime.now()
        self._conversation_id: Optional[str] = None
        self._adapter_entered: bool = False  # Track if context manager is active

    async def close(self) -> None:
        """Clean up resources and close the adapter."""
        if self.adapter and self._adapter_entered:
            try:
                await self.adapter.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing adapter: {e}")
            finally:
                self._adapter_entered = False
                self.adapter = None

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session and get initial greeting from Claude.

        Yields message chunks as they stream in.
        """
        # Load the create-spec skill
        skill_path = ROOT_DIR / ".claude" / "commands" / "create-spec.md"

        if not skill_path.exists():
            yield {
                "type": "error",
                "content": f"Spec creation skill not found at {skill_path}"
            }
            return

        try:
            skill_content = skill_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skill_content = skill_path.read_text(encoding="utf-8", errors="replace")

        # Ensure project directory exists (like CLI does in start.py)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Delete app_spec.txt so Claude can create it fresh
        # The SDK requires reading existing files before writing, but app_spec.txt is created new
        # Note: We keep initializer_prompt.md so Claude can read and update the template
        from autoforge_paths import get_prompts_dir
        prompts_dir = get_prompts_dir(self.project_dir)
        app_spec_path = prompts_dir / "app_spec.txt"
        if app_spec_path.exists():
            app_spec_path.unlink()
            logger.info("Deleted scaffolded app_spec.txt for fresh spec creation")

        # Create security settings file (like client.py does)
        # This grants permissions for file operations in the project directory
        security_settings = {
            "sandbox": {"enabled": False},  # Disable sandbox for spec creation
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [
                    "Read(./**)",
                    "Write(./**)",
                    "Edit(./**)",
                    "Glob(./**)",
                ],
            },
        }
        from autoforge_paths import get_claude_settings_path
        settings_file = get_claude_settings_path(self.project_dir)
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        # Replace $ARGUMENTS with absolute project path (like CLI does in start.py:184)
        # Using absolute path avoids confusion when project folder name differs from app name
        project_path = str(self.project_dir.resolve())
        system_prompt = skill_content.replace("$ARGUMENTS", project_path)

        # Write system prompt to CLAUDE.md file to avoid Windows command line length limit
        # The SDK will read this via setting_sources=["project"]
        claude_md_path = self.project_dir / "CLAUDE.md"
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(system_prompt)
        logger.info(f"Wrote system prompt to {claude_md_path}")

        # Create Claude SDK client with limited tools for spec creation
        # Use Opus for best quality spec generation
        # Use system Claude CLI to avoid bundled Bun runtime crash (exit code 3) on Windows
        system_cli = shutil.which("claude")

        # Build environment overrides for API configuration
        from registry import DEFAULT_MODEL, get_effective_sdk_env
        from sdk_adapter.factory import get_sdk_type
        sdk_env = get_effective_sdk_env()

        # Determine model based on SDK type
        sdk_type = get_sdk_type()
        if sdk_type == "codex":
            # Codex SDK uses its own default model - don't specify
            model = None
        else:
            # Claude SDK uses Anthropic models
            model = sdk_env.get("ANTHROPIC_DEFAULT_OPUS_MODEL") or os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL") or DEFAULT_MODEL or "claude-opus-4-6"

        try:
            options = AdapterOptions(
                model=model,
                project_dir=self.project_dir,
                cli_path=system_cli,
                # System prompt loaded from CLAUDE.md via setting_sources
                # Include "user" for global skills and subagents from ~/.claude/
                setting_sources=["project"],
                include_user_settings=True,  # Adds "user" to setting_sources
                allowed_tools=[
                    "Read",
                    "Write",
                    "Edit",
                    "Glob",
                    "WebFetch",
                    "WebSearch",
                ],
                permission_mode="acceptEdits",  # Auto-approve file writes for spec creation
                max_turns=100,
                cwd=str(self.project_dir.resolve()),
                settings_file=str(settings_file.resolve()),
                env=sdk_env,
            )
            self.adapter = create_adapter(options)
            # Enter the async context and track it
            await self.adapter.__aenter__()
            self._adapter_entered = True
        except Exception as e:
            logger.exception("Failed to create adapter")
            yield {
                "type": "error",
                "content": f"Failed to initialize adapter: {str(e)}"
            }
            return

        # Start the conversation - the agent will send the Phase 1 greeting
        try:
            async for chunk in self._query_adapter("Begin the spec creation process."):
                yield chunk
            # Signal that the response is complete (for UI to hide loading indicator)
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Failed to start spec chat")
            yield {
                "type": "error",
                "content": f"Failed to start conversation: {str(e)}"
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
            - {"type": "question", "questions": list}
            - {"type": "spec_complete", "path": str}
            - {"type": "error", "content": str}
        """
        if not self.adapter:
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
            async for chunk in self._query_adapter(user_message, attachments):
                yield chunk
            # Signal that the response is complete (for UI to hide loading indicator)
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during adapter query")
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }

    async def _query_adapter(
        self,
        message: str,
        attachments: list[ImageAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Internal method to query the adapter and stream responses.

        Handles tool calls (Write) and text responses using unified event model.
        Supports multimodal content with image attachments.

        IMPORTANT: Spec creation requires BOTH files to be written:
        1. app_spec.txt - the main specification
        2. initializer_prompt.md - tells the agent how many features to create

        We only signal spec_complete when BOTH files are verified on disk.
        """
        if not self.adapter:
            return

        # Build the message content
        if attachments and len(attachments) > 0:
            # Multimodal message: build content blocks array
            content_blocks: list[dict[str, Any]] = []

            # Add text block if there's text
            if message:
                content_blocks.append({"type": "text", "text": message})

            # Add image blocks
            for att in attachments:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att.mimeType,
                        "data": att.base64Data,
                    }
                })

            # Send multimodal content to adapter
            await self.adapter.query(content_blocks)
            logger.info(f"Sent multimodal message with {len(attachments)} image(s)")
        else:
            # Text-only message: use string format
            await self.adapter.query(message)

        current_text = ""

        # Track pending writes for BOTH required files
        pending_writes: dict[str, dict[str, Any] | None] = {
            "app_spec": None,      # {"tool_id": ..., "path": ...}
            "initializer": None,   # {"tool_id": ..., "path": ...}
        }

        # Track which files have been successfully written
        files_written = {
            "app_spec": False,
            "initializer": False,
        }

        # Store paths for the completion message
        spec_path = None

        # Stream the response using unified events
        async for event in self.adapter.receive_events():
            if event.type == EventType.TEXT:
                # Accumulate text and yield it
                if event.content:
                    current_text += event.content
                    yield {"type": "text", "content": event.content}

                    # Store in message history
                    self.messages.append({
                        "role": "assistant",
                        "content": event.content,
                        "timestamp": datetime.now().isoformat()
                    })

            elif event.type == EventType.TOOL_CALL:
                tool_name = event.tool_name or ""
                tool_input = event.tool_input
                tool_id = event.tool_id or ""

                if tool_name in ("Write", "Edit"):
                    # File being written or edited - track for verification
                    file_path = tool_input.get("file_path", "")

                    # Track app_spec.txt
                    if "app_spec.txt" in str(file_path):
                        pending_writes["app_spec"] = {
                            "tool_id": tool_id,
                            "path": file_path
                        }
                        logger.info(f"{tool_name} tool called for app_spec.txt: {file_path}")

                    # Track initializer_prompt.md
                    elif "initializer_prompt.md" in str(file_path):
                        pending_writes["initializer"] = {
                            "tool_id": tool_id,
                            "path": file_path
                        }
                        logger.info(f"{tool_name} tool called for initializer_prompt.md: {file_path}")

            elif event.type == EventType.TOOL_RESULT:
                tool_use_id = event.tool_id or ""
                is_error = event.is_error

                if is_error:
                    logger.warning(f"Tool error: {event.content}")
                    # Clear any pending writes that failed
                    for key in pending_writes:
                        pending_write = pending_writes[key]
                        if pending_write is not None and tool_use_id == pending_write.get("tool_id"):
                            logger.error(f"{key} write failed: {event.content}")
                            pending_writes[key] = None
                else:
                    # Tool succeeded - check which file was written

                    # Check app_spec.txt
                    if pending_writes["app_spec"] and tool_use_id == pending_writes["app_spec"].get("tool_id"):
                        file_path = pending_writes["app_spec"]["path"]
                        full_path = Path(file_path) if Path(file_path).is_absolute() else self.project_dir / file_path
                        if full_path.exists():
                            logger.info(f"app_spec.txt verified at: {full_path}")
                            files_written["app_spec"] = True
                            spec_path = file_path

                            # Notify about file write (but NOT completion yet)
                            yield {
                                "type": "file_written",
                                "path": str(file_path)
                            }
                        else:
                            logger.error(f"app_spec.txt not found after write: {full_path}")
                        pending_writes["app_spec"] = None

                    # Check initializer_prompt.md
                    if pending_writes["initializer"] and tool_use_id == pending_writes["initializer"].get("tool_id"):
                        file_path = pending_writes["initializer"]["path"]
                        full_path = Path(file_path) if Path(file_path).is_absolute() else self.project_dir / file_path
                        if full_path.exists():
                            logger.info(f"initializer_prompt.md verified at: {full_path}")
                            files_written["initializer"] = True

                            # Notify about file write
                            yield {
                                "type": "file_written",
                                "path": str(file_path)
                            }
                        else:
                            logger.error(f"initializer_prompt.md not found after write: {full_path}")
                        pending_writes["initializer"] = None

                    # Check if BOTH files are now written - only then signal completion
                    if files_written["app_spec"] and files_written["initializer"]:
                        logger.info("Both app_spec.txt and initializer_prompt.md verified - signaling completion")
                        self.complete = True
                        yield {
                            "type": "spec_complete",
                            "path": str(spec_path)
                        }

            elif event.type == EventType.ERROR:
                yield {"type": "error", "content": event.content}

            elif event.type == EventType.DONE:
                break

    def is_complete(self) -> bool:
        """Check if spec creation is complete."""
        return self.complete

    def get_messages(self) -> list[dict]:
        """Get all messages in the conversation."""
        return self.messages.copy()


# Session registry with thread safety
_sessions: dict[str, SpecChatSession] = {}
_sessions_lock = threading.Lock()


def get_session(project_name: str) -> Optional[SpecChatSession]:
    """Get an existing session for a project."""
    with _sessions_lock:
        return _sessions.get(project_name)


async def create_session(project_name: str, project_dir: Path) -> SpecChatSession:
    """Create a new session for a project, closing any existing one.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
    """
    old_session: Optional[SpecChatSession] = None

    with _sessions_lock:
        # Get existing session to close later (outside the lock)
        old_session = _sessions.pop(project_name, None)
        session = SpecChatSession(project_name, project_dir)
        _sessions[project_name] = session

    # Close old session outside the lock to avoid blocking
    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old session for {project_name}: {e}")

    return session


async def remove_session(project_name: str) -> None:
    """Remove and close a session."""
    session: Optional[SpecChatSession] = None

    with _sessions_lock:
        session = _sessions.pop(project_name, None)

    # Close session outside the lock
    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session for {project_name}: {e}")


def list_sessions() -> list[str]:
    """List all active session project names."""
    with _sessions_lock:
        return list(_sessions.keys())


async def cleanup_all_sessions() -> None:
    """Close all active sessions. Called on server shutdown."""
    sessions_to_close: list[SpecChatSession] = []

    with _sessions_lock:
        sessions_to_close = list(_sessions.values())
        _sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session {session.project_name}: {e}")
