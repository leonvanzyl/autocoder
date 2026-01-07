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

from .assistant_database import (
    create_conversation,
    add_message,
    get_conversation,
    get_messages,
)

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Feature MCP tools available to assistant
ASSISTANT_FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_next",
    "mcp__features__feature_get_all",  # Get all features
    "mcp__features__feature_get_by_id",  # Get specific feature
    "mcp__features__feature_get_for_regression",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_update",  # Modify features
    "mcp__features__feature_delete",  # Remove features
]

# Playwright MCP tools for browser automation
ASSISTANT_PLAYWRIGHT_TOOLS = [
    # Core navigation & screenshots
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_snapshot",

    # Element interaction
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_press_key",

    # JavaScript & debugging
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_console_messages",

    # Browser management
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_tabs",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_handle_dialog",
]

# Built-in tools for assistant (no Write, Edit, Bash - still can't modify files)
ASSISTANT_BUILTIN_TOOLS = [
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

    return f"""You are a helpful project assistant for the "{project_name}" project.

Your role is to help users plan features, understand the codebase, answer questions, and organize work into features.

IMPORTANT CAPABILITIES:
- You CAN read and analyze source code files
- You CAN search the codebase for patterns
- You CAN look up documentation online
- You CAN check feature progress and status
- You CAN create new features based on user discussions
- You CAN visit pages in a browser to test the application
- You CAN take screenshots to show UI state
- You CANNOT modify files directly (use the coding agent for implementation)

## When Users Want to Implement Something:

1. **Discuss the plan** - Understand what they want to build
2. **Break it down** - Split into manageable features
3. **Test the current state** - Use browser tools to visit the app if running
4. **Create features** - Use feature_create_bulk to add them to the database
5. **Explain** - Tell them to start the coding agent to implement

## Project Specification

{app_spec_content if app_spec_content else "(No app specification found)"}

## Available Tools

You have access to these tools:
- **Read**: Read file contents
- **Glob**: Find files by pattern (e.g., "**/*.tsx")
- **Grep**: Search file contents with regex
- **WebFetch/WebSearch**: Look up documentation online
- **Browser Tools**: Navigate to pages, take screenshots, click buttons, fill forms
- **feature_get_stats**: Get feature completion progress
- **feature_get_next**: See the next pending feature
- **feature_get_all**: Get ALL features with full details
- **feature_get_by_id**: Get a specific feature's details
- **feature_get_for_regression**: See passing features
- **feature_create_bulk**: Create multiple features at once
- **feature_update**: Modify an existing feature
- **feature_delete**: Remove a feature

## Guidelines

1. Be concise and helpful
2. When planning features, be specific and actionable
3. **ALWAYS ask for confirmation before creating/modifying/deleting features** - show the user what you plan to do and get their approval
4. Use feature_get_all FIRST to see the current feature list before suggesting changes
5. Each feature should have: category, name, description, and implementation steps
6. Reference specific file paths and line numbers when discussing code
7. After creating features, remind the user to start the coding agent
8. **Use browser tools to verify the current state** before suggesting changes
9. **Take screenshots to show visual issues** when debugging UI problems

## Browser Automation

You can visit and interact with web pages:
- **Navigate** to localhost URLs to test the application
- **Take screenshots** to show the user what something looks like
- **Click elements** and **fill forms** to test functionality
- **Evaluate JavaScript** to check state or console messages
- **Resize viewport** to test responsive design

Always close browser tabs when done to free resources.

## Smart Feature Management

When a user wants to add/modify features:
1. Use feature_get_all to see the current feature list
2. If discussing UI, visit the page and take a screenshot to see current state
3. Analyze what exists vs what the user wants
4. Suggest SPECIFIC changes:
   - "I'll ADD these new features..."
   - "I'll MODIFY feature #5 to include..."
   - "I'll DELETE feature #12 because it's a duplicate..."
5. Get confirmation before making ANY changes
6. After changes, summarize what was done

## Example Workflows

### Planning New Features:
User: "I want to add user authentication"
You: [Uses feature_get_all to see current features]
You: "I can see you have 15 features. I'll add authentication features:
1. Design database schema for users
2. Implement login API endpoint
3. Create login UI
4. Add session management

Should I add these 4 features?"
User: "Yes"
You: [Uses feature_create_bulk to add the features]
You: "I've added 4 features. You now have 19 total. Start the coding agent to implement them!"

### Debugging UI Issues:
User: "The dark mode toggle isn't working"
You: [Navigates to localhost:3000, takes screenshot]
You: "I can see the toggle button exists. Let me test it..."
You: [Clicks the toggle, waits, takes another screenshot]
You: "I clicked the toggle but the theme didn't change. Looking at the console,
I see an error: 'theme is not defined'. Should I add a feature to fix the theme
persistence in localStorage?"

### Modifying Existing Features:
User: "Wait, I want to change the login to use JWT"
You: [Uses feature_get_all again]
You: "I'll modify feature #2 'Implement login API endpoint' to use JWT tokens instead of sessions. Confirm?"
User: "Yes"
You: [Uses feature_update to modify feature #2]
You: "Updated! The coding agent will now implement JWT-based login."
"""


class AssistantChatSession:
    """
    Manages an assistant conversation for a project.

    Uses Claude Opus 4.5 with planning and feature creation capabilities.
    Can read code and create features, but cannot modify files.
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
        self._is_resuming = conversation_id is not None

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
        Yields message chunks as they stream in.
        """
        # Create a new conversation if we don't have one
        if self.conversation_id is None:
            conv = create_conversation(self.project_dir, self.project_name)
            self.conversation_id = conv.id
            yield {"type": "conversation_created", "conversation_id": self.conversation_id}

        # Build permissions list for assistant
        permissions_list = [
            "Read(./**)",
            "Glob(./**)",
            "Grep(./**)",
            "WebFetch",
            "WebSearch",
            *ASSISTANT_FEATURE_MCP_TOOLS,
            *ASSISTANT_PLAYWRIGHT_TOOLS,
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

        # Build MCP servers config - features and Playwright
        mcp_servers = {
            "features": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.feature_mcp"],
                "env": {
                    **os.environ,
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
            "playwright": {
                "command": "npx",
                "args": ["@playwright/mcp@latest", "--viewport-size", "1280x720"],
            },
        }

        # Get system prompt with project context
        system_prompt = get_system_prompt(self.project_name, self.project_dir)

        # Use system Claude CLI
        system_cli = shutil.which("claude")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-opus-4-5-20251101",
                    cli_path=system_cli,
                    system_prompt=system_prompt,
                    allowed_tools=[*ASSISTANT_BUILTIN_TOOLS, *ASSISTANT_FEATURE_MCP_TOOLS, *ASSISTANT_PLAYWRIGHT_TOOLS],
                    mcp_servers=mcp_servers,
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    max_buffer_size=10 * 1024 * 1024,  # 10MB for Playwright screenshots
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception as e:
            logger.exception("Failed to create Claude client")
            yield {"type": "error", "content": f"Failed to initialize assistant: {str(e)}"}
            return

        # If resuming an existing conversation, load history into context
        if self._is_resuming and self.conversation_id:
            try:
                history = get_messages(self.project_dir, self.conversation_id)
                if history:
                    # Build conversation context string with FULL messages
                    context_lines = ["This is our previous conversation history. Review it so you can continue effectively:"]
                    for msg in history:
                        role_name = "User" if msg["role"] == "user" else "Assistant"
                        # Include the FULL message content - no truncation!
                        context_lines.append(f"{role_name}: {msg['content']}")

                    context_prompt = "\n\n".join(context_lines)
                    context_prompt += "\n\nEnd of conversation history. Please review this and continue our conversation naturally. Do not repeat your greeting or summarize unless asked."

                    # Send context to Claude
                    await self.client.query(context_prompt)

                    # Consume the response (we don't need to stream it)
                    async for _ in self.client.receive_response():
                        pass

                    logger.info(f"Loaded {len(history)} messages into context for conversation {self.conversation_id}")
            except Exception as e:
                logger.exception(f"Failed to load conversation history: {e}")
                yield {"type": "error", "content": f"Warning: Could not load full conversation history: {str(e)}"}

        # Send initial greeting only for new conversations
        if not self._is_resuming:
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
            # Just send response_done when resuming
            yield {"type": "response_done"}

    async def send_message(self, user_message: str, attachments: list[dict] = None) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Args:
            user_message: The user's message
            attachments: Optional list of image attachments with base64 data

        Yields:
            Message chunks:
            - {"type": "text", "content": str}
            - {"type": "tool_call", "tool": str, "input": dict}
            - {"type": "response_done"}
            - {"type": "error", "content": str}
        """
        if not self.client:
            yield {"type": "error", "content": "Session not initialized. Call start() first."}
            return

        if self.conversation_id is None:
            yield {"type": "error", "content": "No conversation ID set."}
            return

        # Store user message in database
        add_message(self.project_dir, self.conversation_id, "user", user_message)

        try:
            async for chunk in self._query_claude(user_message, attachments or []):
                yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during Claude query")
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def _query_claude(self, message: str, attachments: list[dict] = None) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Handles tool calls and text responses.

        Args:
            message: The user's text message
            attachments: Optional list of image attachments with base64 data
        """
        if not self.client:
            return

        # Build content list with text and optional images
        content = [{"type": "text", "text": message}]

        # Add image attachments
        if attachments:
            for attachment in attachments:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": attachment.get("mimeType", "image/jpeg"),
                        "data": attachment.get("base64Data", "")
                    }
                })

        # Send message to Claude (with images if present)
        if len(content) > 1:
            # Has images, send as structured content
            await self.client.query(content[0]["text"], images=[{
                "type": "base64",
                "media_type": att["mimeType"],
                "data": att["base64Data"]
            } for att in attachments])
        else:
            # Text only
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
