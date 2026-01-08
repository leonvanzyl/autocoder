"""
Chat-to-Features Session
========================

Manages conversational feature suggestion sessions with Claude.
Loads project context and helps users generate structured feature definitions
from natural language descriptions.
"""

import json
import logging
import os
import re
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from api.database import Feature, create_database
from .chat_to_features_database import (
    add_message,
    add_suggestion,
    get_or_create_conversation,
    load_conversation_history,
    update_suggestion_status,
    clear_conversation,
)

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Feature parsing pattern
FEATURE_PATTERN = re.compile(
    r'---FEATURE_START---\s*'
    r'NAME:\s*(.+?)\s*'
    r'CATEGORY:\s*(.+?)\s*'
    r'DESCRIPTION:\s*(.+?)\s*'
    r'STEPS:\s*(.+?)\s*'
    r'REASONING:\s*(.+?)\s*'
    r'---FEATURE_END---',
    re.DOTALL
)

# Read-only tools for chat context
READONLY_TOOLS = [
    "Read",
    "Glob",
    "Grep",
]


def _parse_numbered_list(text: str) -> list[str]:
    """
    Parse a numbered list from text.

    Handles both:
    - Explicit numbered format: "1. Step one\n2. Step two"
    - Newline-separated list: "Step one\nStep two"

    Args:
        text: Text containing numbered steps

    Returns:
        List of step strings (without numbers)
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    steps = []

    for line in lines:
        # Remove leading number and dot/paren
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
        if cleaned:
            steps.append(cleaned)

    return steps


class ChatToFeaturesSession:
    """
    Manages a chat-to-features conversation for one project.

    Loads project context (app_spec, context files, existing features)
    and guides the user through conversational feature creation.
    """

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the session.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.client: Optional[ClaudeSDKClient] = None
        self.messages: list[dict] = []
        self.created_at = datetime.now()
        self._client_entered: bool = False
        self._context: Optional[str] = None
        self._feature_suggestions: dict[int, dict] = {}  # index -> feature data
        self._conversation_id: Optional[int] = None
        self._next_suggestion_index: int = 0

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

    async def _load_context(self) -> str:
        """
        Load project context from multiple sources.

        Loads:
        1. app_spec.txt from prompts directory
        2. Context files from prompts/context/*.md
        3. Existing features summary (grouped by category)

        Returns:
            Combined context string for the system prompt
        """
        context_parts = []

        # 1. Load app_spec.txt if exists
        spec_path = self.project_dir / "prompts" / "app_spec.txt"
        if spec_path.exists():
            try:
                spec_content = spec_path.read_text(encoding="utf-8")
                # Truncate if too large
                if len(spec_content) > 10000:
                    spec_content = spec_content[:10000] + "\n... (truncated)"
                context_parts.append(f"## Application Specification\n\n{spec_content}")
            except Exception as e:
                logger.warning(f"Failed to read app_spec.txt: {e}")

        # 2. Load context files from analyzer
        context_dir = self.project_dir / "prompts" / "context"
        if context_dir.exists():
            # Load context files in priority order
            priority_files = ["_index", "architecture", "database_schema", "api_endpoints"]
            all_files = {f.stem: f for f in context_dir.glob("*.md") if f.is_file()}

            loaded = set()
            for name in priority_files:
                if name in all_files:
                    try:
                        content = all_files[name].read_text(encoding="utf-8")
                        # Truncate large files
                        if len(content) > 5000:
                            content = content[:5000] + "\n... (truncated)"
                        context_parts.append(f"## Context: {name}\n\n{content}")
                        loaded.add(name)
                    except Exception as e:
                        logger.warning(f"Failed to read context file {name}: {e}")

            # Load remaining files (up to a limit)
            remaining = [f for stem, f in sorted(all_files.items()) if stem not in loaded]
            for f in remaining[:3]:  # Only load 3 more to avoid context overflow
                try:
                    content = f.read_text(encoding="utf-8")
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    context_parts.append(f"## Context: {f.stem}\n\n{content}")
                except Exception as e:
                    logger.warning(f"Failed to read context file {f.name}: {e}")

        # 3. Load existing features summary
        features = self._get_existing_features()
        if features:
            features_summary = self._format_features_summary(features)
            context_parts.append(features_summary)

        return "\n\n---\n\n".join(context_parts) if context_parts else "(No project context available)"

    def _get_existing_features(self) -> list[Feature]:
        """
        Load existing features from the database.

        Returns:
            List of Feature objects (up to 100 most recent)
        """
        db_path = self.project_dir / "features.db"
        if not db_path.exists():
            return []

        try:
            engine, SessionLocal = create_database(self.project_dir)
            session = SessionLocal()
            try:
                # Get features ordered by priority, limited to 100
                features = session.query(Feature).order_by(Feature.priority).limit(100).all()
                return features
            finally:
                session.close()
                engine.dispose()
        except Exception as e:
            logger.warning(f"Failed to load existing features: {e}")
            return []

    def _format_features_summary(self, features: list[Feature]) -> str:
        """
        Format existing features as a summary grouped by category.

        Args:
            features: List of Feature objects

        Returns:
            Formatted string with features grouped by category
        """
        if not features:
            return ""

        # Group by category
        by_category = {}
        for f in features:
            if f.category not in by_category:
                by_category[f.category] = []
            by_category[f.category].append(f)

        lines = [f"## Existing Features ({len(features)} total)\n"]

        for category in sorted(by_category.keys()):
            category_features = by_category[category]
            lines.append(f"\n### {category} ({len(category_features)} features)")

            for f in category_features[:10]:  # Show max 10 per category
                status = "✓" if f.passes else "○"
                lines.append(f"- {status} {f.name}")

            if len(category_features) > 10:
                lines.append(f"  ... and {len(category_features) - 10} more")

        return "\n".join(lines)

    def _build_system_prompt(self, context: str) -> str:
        """
        Build the system prompt for Claude.

        Args:
            context: The loaded project context

        Returns:
            Complete system prompt string
        """
        # Get feature count for stats
        features = self._get_existing_features()
        feature_count = len(features)

        # Get categories for guidance
        categories = set(f.category for f in features) if features else set()
        categories_text = ", ".join(sorted(categories)) if categories else "None yet"

        return f"""You are a feature suggestion assistant for the "{self.project_name}" software project.

# Your Role

Help the user expand their project by suggesting well-designed features that fit the existing architecture. When users describe what they want in natural language, you analyze the request and suggest structured feature definitions.

# Project Context

{context}

# Current State

- **Total Features**: {feature_count}
- **Existing Categories**: {categories_text}

# How to Suggest Features

When you identify a good feature to suggest, output it in this EXACT format:

---FEATURE_START---
NAME: Brief 5-10 word feature name
CATEGORY: Use existing category or create new one
DESCRIPTION: 2-3 sentences explaining what this feature does and why it's valuable
STEPS:
1. First verification step
2. Second verification step
3. Third verification step
REASONING: Why this feature makes sense for this project
---FEATURE_END---

IMPORTANT:
- Use EXACTLY this format with the delimiters `---FEATURE_START---` and `---FEATURE_END---`
- Each section must be on its own line
- STEPS should be numbered and specific enough to test
- You can suggest multiple features per response

# Guidelines

1. **Break down large requests**: If user asks for something complex like "authentication system", break it into multiple focused features:
   - Feature 1: Basic login form with email/password
   - Feature 2: JWT token generation and validation
   - Feature 3: Password reset flow
   - Feature 4: OAuth integration with Google

2. **Complement existing features**: Look at what already exists and suggest features that build on or complement them

3. **Use consistent categories**: Prefer existing categories over creating new ones. Common categories:
   - Authentication
   - User Management
   - API
   - UI/UX
   - Database
   - Testing
   - DevOps

4. **Write testable steps**: Each step should be something concrete the agent can verify:
   - Good: "Navigate to /login and verify form renders with email and password fields"
   - Bad: "Make sure login works"

5. **Explain your reasoning**: Help the user understand why each feature makes sense:
   - How it fits the architecture
   - What problem it solves
   - What dependencies it has

6. **Be conversational**: Talk with the user naturally. Ask clarifying questions when needed. Explain trade-offs.

Now, let's help the user define their features!"""

    def parse_feature_suggestions(self, text: str) -> list[dict]:
        """
        Extract feature suggestions from Claude's response.

        Uses regex to find features in the structured format between
        ---FEATURE_START--- and ---FEATURE_END--- markers.

        Args:
            text: Claude's response text

        Returns:
            List of feature dicts with keys: name, category, description, steps, reasoning
        """
        features = []

        for match in FEATURE_PATTERN.finditer(text):
            try:
                # Parse the steps list
                steps_text = match.group(4)
                steps = _parse_numbered_list(steps_text)

                # Only include features with valid steps
                if steps:
                    features.append({
                        "name": match.group(1).strip(),
                        "category": match.group(2).strip(),
                        "description": match.group(3).strip(),
                        "steps": steps,
                        "reasoning": match.group(5).strip()
                    })
                else:
                    logger.warning(f"Feature '{match.group(1).strip()}' has no valid steps, skipping")

            except Exception as e:
                logger.warning(f"Failed to parse feature suggestion: {e}")
                continue

        return features

    def get_conversation_history(self) -> dict:
        """
        Get conversation history from database for sending to client on reconnect.

        Returns:
            Dict with messages and pending_suggestions
        """
        return load_conversation_history(self.project_dir, self.project_name)

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session with the Claude client.

        Loads project context and sends initial greeting.
        Yields message chunks as they stream in.
        """
        # Initialize database conversation
        try:
            conversation = get_or_create_conversation(self.project_dir, self.project_name)
            self._conversation_id = conversation.id
            logger.info(f"Using conversation ID: {self._conversation_id}")

            # Load existing history
            history = load_conversation_history(self.project_dir, self.project_name)
            if history["messages"]:
                # Restore in-memory state from database
                self.messages = [
                    {"role": m["role"], "content": m["content"], "timestamp": m["timestamp"]}
                    for m in history["messages"]
                ]
                # Restore pending suggestions
                for s in history["pending_suggestions"]:
                    self._feature_suggestions[s["index"]] = s
                    self._next_suggestion_index = max(self._next_suggestion_index, s["index"] + 1)

                # Send history to client
                yield {"type": "history", "data": history}
                logger.info(f"Restored {len(history['messages'])} messages from database")
        except Exception as e:
            logger.warning(f"Could not initialize database conversation: {e}")

        # Load context once at start
        logger.info(f"Loading context for project: {self.project_name}")
        self._context = await self._load_context()
        logger.info(f"Context loaded: {len(self._context)} characters")

        # Build system prompt with context
        system_prompt = self._build_system_prompt(self._context)

        # Create security settings file
        security_settings = {
            "sandbox": {"enabled": False},
            "permissions": {
                "defaultMode": "bypassPermissions",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                ],
            },
        }
        settings_file = self.project_dir / ".claude_chat_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        # Use system Claude CLI
        system_cli = shutil.which("claude")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-sonnet-4-5-20250929",  # Sonnet for speed
                    cli_path=system_cli,
                    system_prompt=system_prompt,
                    allowed_tools=READONLY_TOOLS,
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception as e:
            logger.exception("Failed to create Claude client")
            yield {"type": "error", "content": f"Failed to initialize chat: {str(e)}"}
            return

        # Send initial greeting only for new conversations
        if not self.messages:
            try:
                greeting = f"Hello! I'm here to help you add features to **{self.project_name}**. I've reviewed your project context and existing features. What would you like to build next?"

                # Store the greeting in memory
                self.messages.append({
                    "role": "assistant",
                    "content": greeting,
                    "timestamp": datetime.now().isoformat()
                })

                # Save to database
                if self._conversation_id:
                    try:
                        add_message(self.project_dir, self._conversation_id, "assistant", greeting)
                    except Exception as db_err:
                        logger.warning(f"Failed to save greeting to database: {db_err}")

                yield {"type": "text", "content": greeting}
                yield {"type": "response_done"}
            except Exception as e:
                logger.exception("Failed to send greeting")
                yield {"type": "error", "content": f"Failed to start conversation: {str(e)}"}

    async def send_message(self, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Parses feature suggestions from the response and yields them
        as structured objects.

        Args:
            user_message: The user's message

        Yields:
            Message chunks:
            - {"type": "text", "content": str}
            - {"type": "feature_suggestion", "index": int, "feature": dict}
            - {"type": "response_done"}
            - {"type": "error", "content": str}
        """
        if not self.client:
            yield {"type": "error", "content": "Session not initialized. Call start() first."}
            return

        # Store user message in memory
        self.messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # Save user message to database
        if self._conversation_id:
            try:
                add_message(self.project_dir, self._conversation_id, "user", user_message)
            except Exception as db_err:
                logger.warning(f"Failed to save user message to database: {db_err}")

        try:
            async for chunk in self._query_claude(user_message):
                yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during Claude query")
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def _query_claude(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Handles text responses and parses feature suggestions.
        """
        if not self.client:
            return

        # Send message to Claude
        await self.client.query(message)

        full_response = ""
        feature_index = 0

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

                            # Check for complete feature suggestions in the accumulated text
                            features = self.parse_feature_suggestions(full_response)

                            # Yield any new features we haven't sent yet
                            while feature_index < len(features):
                                feature = features[feature_index]
                                actual_index = self._next_suggestion_index + feature_index
                                # Store the suggestion for later retrieval
                                self._feature_suggestions[actual_index] = feature

                                # Save suggestion to database
                                if self._conversation_id:
                                    try:
                                        add_suggestion(
                                            self.project_dir,
                                            self._conversation_id,
                                            actual_index,
                                            feature["name"],
                                            feature["category"],
                                            feature["description"],
                                            feature["steps"],
                                            feature.get("reasoning")
                                        )
                                    except Exception as db_err:
                                        logger.warning(f"Failed to save suggestion to database: {db_err}")

                                yield {
                                    "type": "feature_suggestion",
                                    "index": actual_index,
                                    "feature": feature
                                }
                                feature_index += 1

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_name = block.name
                        tool_input = getattr(block, "input", {})
                        # Log tool usage but don't yield (read-only operations)
                        logger.info(f"Tool used: {tool_name}")

        # Store the complete response
        if full_response:
            self.messages.append({
                "role": "assistant",
                "content": full_response,
                "timestamp": datetime.now().isoformat()
            })

            # Save assistant response to database
            if self._conversation_id:
                try:
                    add_message(self.project_dir, self._conversation_id, "assistant", full_response)
                except Exception as db_err:
                    logger.warning(f"Failed to save assistant response to database: {db_err}")

            # Update next suggestion index for next call
            self._next_suggestion_index += feature_index

    def get_messages(self) -> list[dict]:
        """Get all messages in the conversation."""
        return self.messages.copy()

    def get_feature_suggestion(self, index: int) -> Optional[dict]:
        """
        Get a feature suggestion by its index.

        Args:
            index: The feature suggestion index

        Returns:
            The feature data dict or None if not found
        """
        return self._feature_suggestions.get(index)

    def remove_feature_suggestion(self, index: int, status: str = "rejected") -> bool:
        """
        Remove a feature suggestion by its index.

        Args:
            index: The feature suggestion index to remove
            status: Status to set in database ("accepted" or "rejected")

        Returns:
            True if removed, False if not found
        """
        if index in self._feature_suggestions:
            del self._feature_suggestions[index]

            # Update status in database
            if self._conversation_id:
                try:
                    update_suggestion_status(
                        self.project_dir,
                        self._conversation_id,
                        index,
                        status
                    )
                except Exception as db_err:
                    logger.warning(f"Failed to update suggestion status in database: {db_err}")

            return True
        return False

    def clear_history(self) -> bool:
        """
        Clear all messages and suggestions from this conversation.

        Returns:
            True if cleared successfully
        """
        # Clear in-memory state
        self.messages.clear()
        self._feature_suggestions.clear()
        self._next_suggestion_index = 0

        # Clear from database
        try:
            return clear_conversation(self.project_dir, self.project_name)
        except Exception as e:
            logger.warning(f"Failed to clear conversation from database: {e}")
            return False


# Session registry with thread safety
_sessions: dict[str, ChatToFeaturesSession] = {}
_sessions_lock = threading.Lock()


def get_session(project_name: str) -> Optional[ChatToFeaturesSession]:
    """Get an existing session for a project."""
    with _sessions_lock:
        return _sessions.get(project_name)


async def create_session(project_name: str, project_dir: Path) -> ChatToFeaturesSession:
    """
    Create a new session for a project, closing any existing one.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
    """
    old_session: Optional[ChatToFeaturesSession] = None

    with _sessions_lock:
        old_session = _sessions.pop(project_name, None)
        session = ChatToFeaturesSession(project_name, project_dir)
        _sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old session for {project_name}: {e}")

    return session


async def remove_session(project_name: str) -> None:
    """Remove and close a session."""
    session: Optional[ChatToFeaturesSession] = None

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
    sessions_to_close: list[ChatToFeaturesSession] = []

    with _sessions_lock:
        sessions_to_close = list(_sessions.values())
        _sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session {session.project_name}: {e}")
