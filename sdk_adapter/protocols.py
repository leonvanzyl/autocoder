"""
SDK Adapter Protocol Definition
===============================

Defines the Protocol (interface) that all SDK adapters must implement.
Using Protocol instead of ABC allows structural subtyping (duck typing).
"""

from typing import AsyncIterator, Protocol, runtime_checkable

from sdk_adapter.types import AgentEvent


@runtime_checkable
class SDKAdapter(Protocol):
    """
    Protocol for SDK adapters providing a unified agent interface.

    All SDK adapters (Claude, Codex) must implement this interface
    to be used interchangeably in AutoForge.

    Usage:
        async with adapter:
            await adapter.query("Your prompt here")
            async for event in adapter.receive_events():
                if event.type == EventType.TEXT:
                    print(event.content)
    """

    async def __aenter__(self) -> "SDKAdapter":
        """Enter async context manager. Initialize SDK resources."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit async context manager. Clean up SDK resources."""
        ...

    async def query(self, message: str | list[dict]) -> None:
        """
        Send a query/prompt to the agent.

        Args:
            message: The prompt text, or a list of content blocks
                     for multimodal input (text + images).
        """
        ...

    def receive_events(self) -> AsyncIterator[AgentEvent]:
        """
        Stream events from the agent response.

        This is an async generator that yields unified AgentEvent objects
        that abstract away SDK-specific event structures.

        Yields:
            AgentEvent objects with types:
            - TEXT: Text content from agent
            - TOOL_CALL: Tool execution started
            - TOOL_RESULT: Tool execution result
            - DONE: Response complete
            - ERROR: Error occurred
        """
        ...

    @property
    def supports_hooks(self) -> bool:
        """
        Whether this SDK supports pre-tool-use hooks.

        Claude SDK: True (supports PreToolUse, PreCompact hooks)
        Codex SDK: False (event-based only, no blocking hooks)

        Returns:
            True if hooks can block tool execution, False otherwise.
        """
        ...
