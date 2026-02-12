"""
Claude Agent SDK Adapter
========================

Wraps the Claude Agent SDK (claude_agent_sdk) to provide
the unified SDKAdapter interface.
"""

from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import HookMatcher

from sdk_adapter.types import AdapterOptions, AgentEvent, EventType


class ClaudeAdapter:
    """
    Adapter for Claude Agent SDK.

    Translates between the unified SDKAdapter interface and
    the Claude Agent SDK's native API.
    """

    def __init__(self, options: AdapterOptions):
        """
        Initialize the Claude adapter.

        Args:
            options: Unified adapter options to configure the client.
        """
        self.options = options
        self._client: ClaudeSDKClient | None = None
        self._build_client()

    def _build_client(self) -> None:
        """Create the underlying ClaudeSDKClient."""
        # Build hooks dict if hook functions are provided
        hooks: dict[str, list[HookMatcher]] = {}

        if self.options.bash_hook:
            hooks["PreToolUse"] = [
                HookMatcher(matcher="Bash", hooks=[self.options.bash_hook])  # type: ignore[list-item]
            ]

        if self.options.compact_hook:
            if "PreCompact" not in hooks:
                hooks["PreCompact"] = []
            hooks["PreCompact"].append(HookMatcher(hooks=[self.options.compact_hook]))  # type: ignore[list-item]

        # Build setting_sources: add "user" if include_user_settings is True
        if self.options.include_user_settings:
            setting_sources = ["project", "user"]
        else:
            setting_sources = self.options.setting_sources

        # Create the Claude SDK client
        self._client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=self.options.model,
                cli_path=self.options.cli_path,
                system_prompt=self.options.system_prompt,
                setting_sources=setting_sources,  # type: ignore[arg-type]
                max_buffer_size=self.options.max_buffer_size,
                allowed_tools=self.options.allowed_tools,
                mcp_servers=self.options.mcp_servers,
                hooks=hooks if hooks else None,  # type: ignore[arg-type]
                max_turns=self.options.max_turns,
                cwd=self.options.cwd,
                settings=self.options.settings_file,
                env=self.options.env,
                betas=self.options.betas if self.options.betas else None,  # type: ignore[arg-type]
                permission_mode=self.options.permission_mode,  # type: ignore[arg-type]
            )
        )

    async def __aenter__(self) -> "ClaudeAdapter":
        """Enter async context manager."""
        if self._client:
            await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def query(self, message: str | list[dict[str, Any]]) -> None:
        """
        Send a query to the Claude agent.

        Args:
            message: The prompt text or multimodal content blocks.
        """
        if self._client:
            await self._client.query(message)  # type: ignore[arg-type]

    async def receive_events(self) -> AsyncIterator[AgentEvent]:
        """
        Stream events from Claude agent, translating to unified AgentEvent.

        The Claude SDK emits AssistantMessage and UserMessage objects
        containing TextBlock, ToolUseBlock, and ToolResultBlock.
        This method translates them to unified AgentEvent objects.
        """
        if not self._client:
            yield AgentEvent(
                type=EventType.ERROR,
                content="Client not initialized",
                is_error=True,
            )
            return

        async for msg in self._client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        yield AgentEvent(
                            type=EventType.TEXT,
                            content=block.text,
                            raw=block,
                        )

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        yield AgentEvent(
                            type=EventType.TOOL_CALL,
                            tool_name=block.name,
                            tool_input=getattr(block, "input", {}) or {},
                            tool_id=getattr(block, "id", None),
                            raw=block,
                        )

            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)

                        yield AgentEvent(
                            type=EventType.TOOL_RESULT,
                            content=str(result_content),
                            tool_id=getattr(block, "tool_use_id", None),
                            is_error=is_error,
                            raw=block,
                        )

        # Signal completion
        yield AgentEvent(type=EventType.DONE)

    @property
    def supports_hooks(self) -> bool:
        """Claude SDK supports PreToolUse and PreCompact hooks."""
        return True
