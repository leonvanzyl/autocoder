"""
Assistant Chat Session
======================

Manages read-only conversational assistant sessions for projects.
The assistant can answer questions about the codebase and features
but cannot modify any files.
"""

import json
import logging
import os
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from dotenv import load_dotenv

from ..gemini_client import is_gemini_configured, stream_chat
from .assistant_database import (
    add_message,
    create_conversation,
    get_messages,
)

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Environment variables to pass through to Claude CLI for API configuration
API_ENV_VARS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "API_TIMEOUT_MS",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
]

# Read-only feature MCP tools
READONLY_FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_by_id",
    "mcp__features__feature_get_ready",
    "mcp__features__feature_get_blocked",
]

# Feature management tools (create/skip but not mark_passing)
FEATURE_MANAGEMENT_TOOLS = [
    "mcp__features__feature_create",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_skip",
]

# Combined list for assistant
ASSISTANT_FEATURE_TOOLS = READONLY_FEATURE_MCP_TOOLS + FEATURE_MANAGEMENT_TOOLS

# Read-only built-in tools (no Write, Edit, Bash)
READONLY_BUILTIN_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
]


def get_system_prompt(project_name: str, project_dir: Path) -> str:
    """Generate the system prompt for the assistant with project context."""
    # Try to load app_spec.txt for context
    app_spec_content = ""
    app_spec_path = project_dir / "prompts" / "app_spec.txt"
    if app_spec_path.exists():
        try:
            app_spec_content = app_spec_path.read_text(encoding="utf-8")
            # Truncate if too long
            if len(app_spec_content) > 5000:
                app_spec_content = app_spec_content[:5000] + "\n... (truncated)"
        except Exception as e:
            logger.warning(f"Failed to read app_spec.txt: {e}")

    return f"""You are a helpful project assistant and backlog manager for the "{project_name}" project.

Your role is to help users understand the codebase, answer questions about features, and manage the project backlog. You can READ files and CREATE/MANAGE features, but you cannot modify source code.

## What You CAN Do

**Codebase Analysis (Read-Only):**
- Read and analyze source code files
- Search for patterns in the codebase
- Look up documentation online
- Check feature progress and status

**Feature Management:**
- Create new features/test cases in the backlog
- Skip features to deprioritize them (move to end of queue)
- View feature statistics and progress

## What You CANNOT Do

- Modify, create, or delete source code files
- Mark features as passing (that requires actual implementation by the coding agent)
- Run bash commands or execute code

If the user asks you to modify code, explain that you're a project assistant and they should use the main coding agent for implementation.

## Project Specification

{app_spec_content if app_spec_content else "(No app specification found)"}

## Available Tools

**Code Analysis:**
- **Read**: Read file contents
- **Glob**: Find files by pattern (e.g., "**/*.tsx")
- **Grep**: Search file contents with regex
- **WebFetch/WebSearch**: Look up documentation online

**Feature Management:**
- **feature_get_stats**: Get feature completion progress
- **feature_get_by_id**: Get details for a specific feature
- **feature_get_ready**: See features ready for implementation
- **feature_get_blocked**: See features blocked by dependencies
- **feature_create**: Create a single feature in the backlog
- **feature_create_bulk**: Create multiple features at once
- **feature_skip**: Move a feature to the end of the queue

## Creating Features

When a user asks to add a feature, gather the following information:
1. **Category**: A grouping like "Authentication", "API", "UI", "Database"
2. **Name**: A concise, descriptive name
3. **Description**: What the feature should do
4. **Steps**: How to verify/implement the feature (as a list)

You can ask clarifying questions if the user's request is vague, or make reasonable assumptions for simple requests.

**Example interaction:**
User: "Add a feature for S3 sync"
You: I'll create that feature. Let me add it to the backlog...
[calls feature_create with appropriate parameters]
You: Done! I've added "S3 Sync Integration" to your backlog. It's now visible on the kanban board.

## Guidelines

1. Be concise and helpful
2. When explaining code, reference specific file paths and line numbers
3. Use the feature tools to answer questions about project progress
4. Search the codebase to find relevant information before answering
5. When creating features, confirm what was created
6. If you're unsure about details, ask for clarification"""


class AssistantChatSession:
    """
    Manages a read-only assistant conversation for a project.

    Uses Claude Opus 4.5 with only read-only tools enabled.
    Persists conversation history to SQLite.
    """

    def __init__(self, project_name: str, project_dir: Path, conversation_id: Optional[int] = None):
        """
        Initialize the session.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory
            conversation_id: Optional existing conversation ID to resume
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.conversation_id = conversation_id
        self.client: Optional[ClaudeSDKClient] = None
        self._client_entered: bool = False
        self.created_at = datetime.now()
        self._history_loaded: bool = False  # Track if we've loaded history for resumed conversations
        self.provider: str = "gemini" if is_gemini_configured() else "claude"
        self._system_prompt: str | None = None

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

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session with the Claude client.

        Creates a new conversation if none exists, then sends an initial greeting.
        For resumed conversations, skips the greeting since history is loaded from DB.
        Yields message chunks as they stream in.
        """
        # Track if this is a new conversation (for greeting decision)
        is_new_conversation = self.conversation_id is None

        # Create a new conversation if we don't have one
        if is_new_conversation:
            conv = create_conversation(self.project_dir, self.project_name)
            self.conversation_id = conv.id
            yield {"type": "conversation_created", "conversation_id": self.conversation_id}

        # Build permissions list for assistant access (read + feature management)
        permissions_list = [
            "Read(./**)",
            "Glob(./**)",
            "Grep(./**)",
            "WebFetch",
            "WebSearch",
            *ASSISTANT_FEATURE_TOOLS,
        ]

        # Create security settings file
        security_settings = {
            "sandbox": {"enabled": False},  # No bash, so sandbox not needed
            "permissions": {
                "defaultMode": "bypassPermissions",  # Read-only, no dangerous ops
                "allow": permissions_list,
            },
        }
        settings_file = self.project_dir / ".claude_assistant_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        # Build MCP servers config - only features MCP for read-only access
        mcp_servers = {
            "features": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.feature_mcp"],
                "env": {
                    # Only specify variables the MCP server needs
                    # (subprocess inherits parent environment automatically)
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
        }

        # Get system prompt with project context
        system_prompt = get_system_prompt(self.project_name, self.project_dir)
        self._system_prompt = system_prompt

        # Write system prompt to CLAUDE.md file to avoid Windows command line length limit
        # The SDK will read this via setting_sources=["project"]
        claude_md_path = self.project_dir / "CLAUDE.md"
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(system_prompt)
        logger.info(f"Wrote assistant system prompt to {claude_md_path}")

        if self.provider == "gemini":
            logger.info("Assistant session using Gemini provider (no tools).")
            self.client = None
        else:
            # Use system Claude CLI
            system_cli = shutil.which("claude")

            # Build environment overrides for API configuration
            sdk_env = {var: os.getenv(var) for var in API_ENV_VARS if os.getenv(var)}

            # Determine model from environment or use default
            # This allows using alternative APIs (e.g., GLM via z.ai) that may not support Claude model names
            model = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-5-20251101")

            try:
                logger.info("Creating ClaudeSDKClient...")
                self.client = ClaudeSDKClient(
                    options=ClaudeAgentOptions(
                        model=model,
                        cli_path=system_cli,
                        # System prompt loaded from CLAUDE.md via setting_sources
                        # This avoids Windows command line length limit (~8191 chars)
                        setting_sources=["project"],
                        allowed_tools=[*READONLY_BUILTIN_TOOLS, *ASSISTANT_FEATURE_TOOLS],
                        mcp_servers=mcp_servers,
                        permission_mode="bypassPermissions",
                        max_turns=100,
                        cwd=str(self.project_dir.resolve()),
                        settings=str(settings_file.resolve()),
                        env=sdk_env,
                    )
                )
                logger.info("Entering Claude client context...")
                await self.client.__aenter__()
                self._client_entered = True
                logger.info("Claude client ready")
            except Exception as e:
                logger.exception("Failed to create Claude client")
                yield {"type": "error", "content": f"Failed to initialize assistant: {str(e)}"}
                return

        # Send initial greeting only for NEW conversations
        # Resumed conversations already have history loaded from the database
        if is_new_conversation:
            # New conversations don't need history loading
            self._history_loaded = True
            try:
                greeting = f"Hello! I'm your project assistant for **{self.project_name}**. I can help you understand the codebase, explain features, and answer questions about the project. What would you like to know?"

                # Store the greeting in the database
                add_message(self.project_dir, self.conversation_id, "assistant", greeting)

                yield {"type": "text", "content": greeting}
                yield {"type": "response_done"}
            except Exception as e:
                logger.exception("Failed to send greeting")
                yield {"type": "error", "content": f"Failed to start conversation: {str(e)}"}
        else:
            # For resumed conversations, history will be loaded on first message
            # _history_loaded stays False so send_message() will include history
            yield {"type": "response_done"}

    async def send_message(self, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Args:
            user_message: The user's message

        Yields:
            Message chunks:
            - {"type": "text", "content": str}
            - {"type": "tool_call", "tool": str, "input": dict}
            - {"type": "response_done"}
            - {"type": "error", "content": str}
        """
        if self.provider != "gemini" and not self.client:
            yield {"type": "error", "content": "Session not initialized. Call start() first."}
            return

        if self.conversation_id is None:
            yield {"type": "error", "content": "No conversation ID set."}
            return

        # Store user message in database
        add_message(self.project_dir, self.conversation_id, "user", user_message)

        # For resumed conversations, include history context in first message
        message_to_send = user_message
        if not self._history_loaded:
            self._history_loaded = True
            history = get_messages(self.project_dir, self.conversation_id)
            # Exclude the message we just added (last one)
            history = history[:-1] if history else []
            # Cap history to last 35 messages to prevent context overload
            history = history[-35:] if len(history) > 35 else history
            if history:
                # Format history as context for Claude
                history_lines = ["[Previous conversation history for context:]"]
                for msg in history:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    content = msg["content"]
                    # Truncate very long messages
                    if len(content) > 500:
                        content = content[:500] + "..."
                    history_lines.append(f"{role}: {content}")
                history_lines.append("[End of history. Continue the conversation:]")
                history_lines.append(f"User: {user_message}")
                message_to_send = "\n".join(history_lines)
                logger.info(f"Loaded {len(history)} messages from conversation history")

        try:
            if self.provider == "gemini":
                async for chunk in self._query_gemini(message_to_send):
                    yield chunk
            else:
                async for chunk in self._query_claude(message_to_send):
                    yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during assistant query")
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def _query_claude(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Handles tool calls and text responses.
        """
        if not self.client:
            return

        # Send message to Claude
        await self.client.query(message)

        full_response = ""

        # Stream the response
        async for msg in self.client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        text = block.text
                        if text:
                            full_response += text
                            yield {"type": "text", "content": text}

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_name = block.name
                        tool_input = getattr(block, "input", {})
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "input": tool_input,
                        }

        # Store the complete response in the database
        if full_response and self.conversation_id:
            add_message(self.project_dir, self.conversation_id, "assistant", full_response)

    async def _query_gemini(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Query Gemini and stream plain-text responses (no tool calls).
        """
        full_response = ""
        try:
            async for text in stream_chat(
                message,
                system_prompt=self._system_prompt,
                model=os.getenv("GEMINI_MODEL"),
            ):
                full_response += text
                yield {"type": "text", "content": text}
        except Exception as e:
            logger.exception("Gemini query failed")
            yield {"type": "error", "content": f"Gemini error: {e}"}
            return

        if full_response and self.conversation_id:
            add_message(self.project_dir, self.conversation_id, "assistant", full_response)

    def get_conversation_id(self) -> Optional[int]:
        """Get the current conversation ID."""
        return self.conversation_id


# Session registry with thread safety
_sessions: dict[str, AssistantChatSession] = {}
_sessions_lock = threading.Lock()


def get_session(project_name: str) -> Optional[AssistantChatSession]:
    """Get an existing session for a project."""
    with _sessions_lock:
        return _sessions.get(project_name)


async def create_session(
    project_name: str,
    project_dir: Path,
    conversation_id: Optional[int] = None
) -> AssistantChatSession:
    """
    Create a new session for a project, closing any existing one.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
        conversation_id: Optional conversation ID to resume
    """
    old_session: Optional[AssistantChatSession] = None

    with _sessions_lock:
        old_session = _sessions.pop(project_name, None)
        session = AssistantChatSession(project_name, project_dir, conversation_id)
        _sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old session for {project_name}: {e}")

    return session


async def remove_session(project_name: str) -> None:
    """Remove and close a session."""
    session: Optional[AssistantChatSession] = None

    with _sessions_lock:
        session = _sessions.pop(project_name, None)

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
    sessions_to_close: list[AssistantChatSession] = []

    with _sessions_lock:
        sessions_to_close = list(_sessions.values())
        _sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session {session.project_name}: {e}")
