"""
Expand Chat Session
===================

Interactive project expansion conversation with Claude.

This is like spec creation chat, but instead of writing files it:
- reads the existing `prompts/app_spec.txt` for context
- asks the user what to add
- creates new features in the project's `agent_system.db` when Claude emits a
  `<features_to_create>` JSON block.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from autocoder.core.database import get_database
from ..schemas import ImageAttachment

logger = logging.getLogger(__name__)

# Environment variables to pass through to Claude CLI for API configuration.
API_ENV_VARS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "API_TIMEOUT_MS",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
]


async def _make_multimodal_message(content_blocks: list[dict]) -> AsyncGenerator[dict, None]:
    """
    Create an async generator that yields a properly formatted multimodal message.
    Matches the format used in `SpecChatSession`.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": content_blocks},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


# Root directory of the repository's `src/` (server/services -> server -> autocoder -> src)
ROOT_DIR = Path(__file__).resolve().parents[3]


def _extract_features_to_create(text: str) -> list[dict[str, Any]]:
    """
    Extract features from one or more <features_to_create> JSON array blocks.

    Deduplicates by feature name (first occurrence wins).
    """
    matches = re.findall(r"<features_to_create>\s*(\[[\s\S]*?\])\s*</features_to_create>", text)
    if not matches:
        return []

    all_features: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for features_json in matches:
        try:
            decoded = json.loads(features_json)
        except json.JSONDecodeError:
            logger.warning("Failed to parse <features_to_create> JSON block")
            continue
        if not isinstance(decoded, list):
            continue
        for item in decoded:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            all_features.append(item)

    return all_features


def _normalize_feature(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    if not name:
        return None

    category = str(raw.get("category") or "functional").strip() or "functional"
    description = str(raw.get("description") or "").strip()

    steps_raw = raw.get("steps") or []
    steps: list[str] = []
    if isinstance(steps_raw, list):
        steps = [str(s).strip() for s in steps_raw if str(s).strip()]

    return {
        "category": category,
        "name": name,
        "description": description,
        "steps": steps,
    }


def _create_features_bulk_with_ids(project_dir: Path, features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Create features in `agent_system.db`, returning a summary list with IDs.
    """
    if not features:
        return []

    db = get_database(str(project_dir))
    created: list[dict[str, Any]] = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(priority), 0) FROM features")
        max_priority = int(cursor.fetchone()[0] or 0)
        current_priority = max_priority + 1

        for raw in features:
            normalized = _normalize_feature(raw)
            if not normalized:
                continue
            cursor.execute(
                """
                INSERT INTO features (name, description, category, steps, priority, status)
                VALUES (?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    normalized["name"],
                    normalized["description"],
                    normalized["category"],
                    json.dumps(normalized["steps"]) if normalized["steps"] else None,
                    current_priority,
                ),
            )
            feature_id = int(cursor.lastrowid)
            created.append(
                {
                    "id": feature_id,
                    "name": normalized["name"],
                    "category": normalized["category"],
                }
            )
            current_priority += 1

        conn.commit()

    return created


class ExpandChatSession:
    """
    Manages a project expansion conversation.

    Unlike spec creation, this session never writes to the project directory; it only
    reads context and creates feature rows in the DB when instructed.
    """

    def __init__(self, project_name: str, project_dir: Path):
        self.project_name = project_name
        self.project_dir = project_dir
        self.client: Optional[ClaudeSDKClient] = None
        self.messages: list[dict] = []
        self.created_at = datetime.now()
        self._client_entered: bool = False
        self.features_created: int = 0
        self.created_feature_ids: list[int] = []
        self._settings_file: Optional[Path] = None
        self._query_lock = asyncio.Lock()
        self._claude_md_backup: str | None = None
        self._claude_md_created: bool = False

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

        claude_md_path = self.project_dir / "CLAUDE.md"
        try:
            if self._claude_md_backup is not None:
                claude_md_path.write_text(self._claude_md_backup, encoding="utf-8")
            elif self._claude_md_created and claude_md_path.exists():
                claude_md_path.unlink()
        except Exception as e:
            logger.warning(f"Error restoring CLAUDE.md: {e}")

        if self._settings_file and self._settings_file.exists():
            try:
                self._settings_file.unlink()
            except Exception as e:
                logger.warning(f"Error removing settings file: {e}")

    async def start(self) -> AsyncGenerator[dict, None]:
        """Initialize session and stream the initial greeting."""
        skill_path = ROOT_DIR / ".claude" / "commands" / "expand-project.md"
        if not skill_path.exists():
            yield {"type": "error", "content": f"Expand project skill not found at {skill_path}"}
            return

        spec_path = self.project_dir / "prompts" / "app_spec.txt"
        if not spec_path.exists():
            yield {"type": "error", "content": "Project has no app_spec.txt. Create a spec first."}
            return

        try:
            skill_content = skill_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skill_content = skill_path.read_text(encoding="utf-8", errors="replace")

        system_cli = shutil.which("claude")
        if not system_cli:
            yield {"type": "error", "content": "Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"}
            return

        # Read-only permission set for expansion.
        security_settings = {
            "sandbox": {"enabled": False},
            "permissions": {
                "defaultMode": "bypassPermissions",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                ],
            },
        }
        settings_file = self.project_dir / f".claude_settings.expand.{uuid.uuid4().hex}.json"
        self._settings_file = settings_file
        settings_file.write_text(json.dumps(security_settings, indent=2), encoding="utf-8")

        project_path = str(self.project_dir.resolve())
        system_prompt = skill_content.replace("$ARGUMENTS", project_path)

        claude_md_path = self.project_dir / "CLAUDE.md"
        if claude_md_path.exists():
            try:
                self._claude_md_backup = claude_md_path.read_text(encoding="utf-8")
            except Exception:
                self._claude_md_backup = None
        else:
            self._claude_md_created = True

        try:
            claude_md_path.write_text(system_prompt, encoding="utf-8")
        except Exception as e:
            yield {"type": "error", "content": f"Failed to write CLAUDE.md: {str(e)}"}
            return

        sdk_env = {var: os.getenv(var) for var in API_ENV_VARS if os.getenv(var)}
        model = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-5-20251101")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model=model,
                    cli_path=system_cli,
                    system_prompt="You are an expert product-minded software architect.",
                    setting_sources=["project"],
                    allowed_tools=["Read", "Glob"],
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                    env=sdk_env,
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception as e:
            logger.exception("Failed to create Claude client for expand session")
            yield {"type": "error", "content": f"Failed to initialize Claude: {str(e)}"}
            return

        try:
            async with self._query_lock:
                async for chunk in self._query_claude("Begin the project expansion process."):
                    yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Failed to start expand chat")
            yield {"type": "error", "content": f"Failed to start conversation: {str(e)}"}

    async def send_message(
        self,
        user_message: str,
        attachments: list[ImageAttachment] | None = None,
    ) -> AsyncGenerator[dict, None]:
        if not self.client:
            yield {"type": "error", "content": "Session not initialized. Call start() first."}
            return

        self.messages.append(
            {
                "role": "user",
                "content": user_message,
                "has_attachments": bool(attachments),
                "timestamp": datetime.now().isoformat(),
            }
        )

        try:
            async with self._query_lock:
                async for chunk in self._query_claude(user_message, attachments):
                    yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during Claude query (expand)")
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def _query_claude(
        self,
        message: str,
        attachments: list[ImageAttachment] | None = None,
    ) -> AsyncGenerator[dict, None]:
        if not self.client:
            return

        if attachments and len(attachments) > 0:
            content_blocks: list[dict[str, Any]] = []
            if message:
                content_blocks.append({"type": "text", "text": message})
            for att in attachments:
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": att.mimeType,
                            "data": att.base64Data,
                        },
                    }
                )
            await self.client.query(_make_multimodal_message(content_blocks))
        else:
            await self.client.query(message)

        full_response = ""

        async for msg in self.client.receive_response():
            if type(msg).__name__ != "AssistantMessage" or not hasattr(msg, "content"):
                continue
            for block in msg.content:
                if type(block).__name__ != "TextBlock" or not hasattr(block, "text"):
                    continue
                text = block.text
                if not text:
                    continue
                full_response += text
                yield {"type": "text", "content": text}
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": text,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        features = _extract_features_to_create(full_response)
        if not features:
            return

        try:
            created = _create_features_bulk_with_ids(self.project_dir, features)
        except Exception:
            logger.exception("Failed to create features from expand session")
            yield {"type": "error", "content": "Failed to create features"}
            return

        if not created:
            return

        self.features_created += len(created)
        self.created_feature_ids.extend([int(f["id"]) for f in created if f.get("id")])

        yield {"type": "features_created", "count": len(created), "features": created}

    def get_features_created(self) -> int:
        return self.features_created

    def get_messages(self) -> list[dict]:
        return self.messages.copy()

    def is_complete(self) -> bool:
        # Expand sessions are user-driven; the UI can end via an explicit "done" message.
        return False


_expand_sessions: dict[str, ExpandChatSession] = {}
_expand_sessions_lock = threading.Lock()


def get_expand_session(project_name: str) -> Optional[ExpandChatSession]:
    with _expand_sessions_lock:
        return _expand_sessions.get(project_name)


async def create_expand_session(project_name: str, project_dir: Path) -> ExpandChatSession:
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
    session: Optional[ExpandChatSession] = None
    with _expand_sessions_lock:
        session = _expand_sessions.pop(project_name, None)

    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session for {project_name}: {e}")


def list_expand_sessions() -> list[str]:
    with _expand_sessions_lock:
        return list(_expand_sessions.keys())


async def cleanup_all_expand_sessions() -> None:
    sessions_to_close: list[ExpandChatSession] = []
    with _expand_sessions_lock:
        sessions_to_close = list(_expand_sessions.values())
        _expand_sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session {session.project_name}: {e}")
