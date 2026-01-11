"""Opencode SDK adapter

Provides a minimal async client wrapper that exposes the methods used by
our agent loop: async context manager, `query(message)` to send a prompt and
`receive_response()` async generator to yield message-like objects.

This keeps the rest of the codebase mostly untouched while using the
`opencode_ai` AsyncOpencode client under the hood.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

try:
    from opencode_ai import AsyncOpencode
except Exception:  # pragma: no cover - best-effort import
    AsyncOpencode = None  # type: ignore


class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class ToolUseBlock:
    def __init__(self, name: str, input: object | None = None) -> None:
        self.name = name
        self.input = input


class ToolResultBlock:
    def __init__(self, content: object | str, is_error: bool = False) -> None:
        self.content = content
        self.is_error = is_error


class AssistantMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class UserMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class OpencodeClient:
    """Minimal adapter around AsyncOpencode.

    Behavior:
    - On __aenter__, creates a session via `client.session.create()`
    - query(message) posts a chat message to the session
    - receive_response() polls messages for the session and yields
      message-like objects compatible with existing agent handling
    """

    def __init__(self, project_dir, model: str, yolo_mode: bool = False):
        if AsyncOpencode is None:
            raise RuntimeError(
                "opencode_ai is not installed. Install with `pip install --pre opencode-ai`"
            )
        self.project_dir = project_dir
        self.model = model
        self.yolo_mode = yolo_mode
        self._client: AsyncOpencode | None = None
        self._session = None

    async def __aenter__(self):
        self._client = AsyncOpencode()
        # Create a fresh session
        self._session = await self._client.session.create()

        # Choose a provider (fallback to first available)
        providers_resp = await self._client.app.providers()
        if getattr(providers_resp, "providers", None):
            self._provider_id = providers_resp.providers[0].id
        else:
            self._provider_id = ""

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            # Best-effort close
            aclose = getattr(self._client, "aclose", None)
            if aclose:
                await aclose()

    async def query(self, message: str) -> None:
        """Send a message to the session."""
        assert self._client is not None and self._session is not None
        # Build a simple text part
        parts = [{"type": "text", "text": message}]

        # Send chat message
        try:
            await self._client.session.chat(
                self._session.id,
                model_id=self.model,
                parts=parts,
                provider_id=self._provider_id,
            )
        except Exception:
            # Send failures should be surfaced to caller via receive_response
            raise

    async def receive_response(self) -> AsyncIterator[object]:
        """Poll and yield session messages as simplified objects.

        Yields objects with type name 'AssistantMessage' or 'UserMessage' and
        .content as list of TextBlock/ToolUseBlock/ToolResultBlock objects.
        """
        assert self._client is not None and self._session is not None

        # Poll messages from the session. We fetch messages repeatedly until no
        # new messages are returned for a short period. This keeps things simple
        # and avoids the complexity of wiring SSE streaming here.
        last_seen = 0
        idle_cycles = 0

        while True:
            items = await self._client.session.messages(self._session.id)
            # items is a list of {info: Message, parts: [Part, ...]}
            if not items:
                idle_cycles += 1
            else:
                idle_cycles = 0

            new_items = items[last_seen:]
            for item in new_items:
                role = getattr(item.info, "role", "assistant")
                parts_out = []
                for part in item.parts:
                    ptype = getattr(part, "type", "text")
                    if ptype == "text":
                        text = getattr(part, "text", "")
                        parts_out.append(TextBlock(text))
                    elif ptype == "tool":
                        tool_name = getattr(part, "tool", "")
                        state = getattr(part, "state", None)
                        # Completed -> ToolResultBlock with output
                        if state and getattr(state, "status", None) == "completed":
                            output = getattr(state, "output", "")
                            parts_out.append(ToolResultBlock(output, is_error=False))
                        elif state and getattr(state, "status", None) == "error":
                            # Some errors are nested; serialize roughly
                            parts_out.append(ToolResultBlock(str(state), is_error=True))
                        else:
                            # For running/pending, expose as ToolUseBlock
                            parts_out.append(ToolUseBlock(tool_name, None))
                    else:
                        # Other parts (step start/finish, snapshots) - stringify
                        parts_out.append(TextBlock(str(part)))

                if role == "assistant":
                    yield AssistantMessage(parts_out)
                else:
                    yield UserMessage(parts_out)

            last_seen = len(items)

            # If no new items for a few cycles, assume conversation done
            if idle_cycles > 3:
                return

            # Small sleep to avoid tight polling loop
            await asyncio.sleep(0.4)
