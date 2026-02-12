"""
Codex SDK Adapter
=================

Wraps the Codex SDK (codex_sdk) to provide
the unified SDKAdapter interface.

Note: Codex SDK uses an event-based model without blocking hooks.
Security relies on Codex's built-in sandboxing and approval policies.
"""

import logging
import shutil
from typing import Any, AsyncIterator

from sdk_adapter.types import AdapterOptions, AgentEvent, EventType

logger = logging.getLogger(__name__)


class CodexAdapter:
    """
    Adapter for OpenAI Codex SDK.

    Translates between the unified SDKAdapter interface and
    the Codex SDK's native API.

    Key differences from Claude:
    - No PreToolUse hooks (event-based only)
    - Uses Thread.run_streamed() instead of query()/receive_response()
    - MCP servers configured via TOML, not dict
    """

    def __init__(self, options: AdapterOptions):
        """
        Initialize the Codex adapter.

        Args:
            options: Unified adapter options to configure the client.
        """
        self.options = options
        self._codex = None
        self._thread = None
        self._pending_message: str | list[dict[str, Any]] = ""
        self._build_client()

    def _build_client(self) -> None:
        """Create the underlying Codex client and thread."""
        try:
            from codex_sdk import ApprovalMode, Codex, SandboxMode
        except ImportError:
            raise ImportError(
                "codex-sdk-py not installed. Install with: pip install codex-sdk-py"
            )

        # Map sandbox mode (Codex uses different enum values)
        sandbox_mode = SandboxMode.WORKSPACE_WRITE
        if self.options.yolo_mode:
            # In YOLO mode, still use workspace-write for safety
            sandbox_mode = SandboxMode.WORKSPACE_WRITE

        # Map permission_mode to ApprovalMode
        # "bypassPermissions" -> NEVER (auto-approve all)
        # "acceptEdits" -> ON_FAILURE (auto-approve, ask on failure)
        if self.options.permission_mode == "bypassPermissions":
            approval_policy = ApprovalMode.NEVER
        else:
            # Default to NEVER for automation (similar to "acceptEdits" behavior)
            approval_policy = ApprovalMode.NEVER

        # Build Codex client options
        codex_options: dict[str, Any] = {}

        if self.options.env:
            codex_options["env"] = self.options.env

        # Always find and set the codex CLI path explicitly
        # (cli_path option is for Claude CLI, not Codex)
        codex_cli = shutil.which("codex")
        if codex_cli:
            codex_options["codex_path_override"] = codex_cli
            print(f"   - Using codex CLI at: {codex_cli}", flush=True)

        # Convert mcp_servers dict to config_overrides for Codex CLI
        # Claude SDK format: {"features": {"command": "...", "args": [...], "env": {...}}}
        # Codex config format: {"mcp_servers": {"features": {"command": "...", "args": [...]}}}
        if self.options.mcp_servers:
            config_overrides: dict[str, Any] = {"mcp_servers": {}}
            for server_name, server_config in self.options.mcp_servers.items():
                config_overrides["mcp_servers"][server_name] = {
                    "command": server_config.get("command", ""),
                    "args": server_config.get("args", []),
                }
                # Add env if present
                if server_config.get("env"):
                    config_overrides["mcp_servers"][server_name]["env"] = server_config["env"]
            codex_options["config"] = config_overrides
            print(f"   - Configured MCP servers for Codex: {list(self.options.mcp_servers.keys())}", flush=True)

        # Create Codex client
        self._codex = Codex(codex_options if codex_options else None)

        # Build thread options
        thread_options: dict[str, Any] = {
            "sandbox_mode": sandbox_mode,
            "skip_git_repo_check": True,
            "approval_policy": approval_policy,
        }

        # Only set model if explicitly specified (Codex has its own default)
        if self.options.model:
            thread_options["model"] = self.options.model

        if self.options.cwd:
            thread_options["working_directory"] = self.options.cwd
        elif self.options.project_dir:
            thread_options["working_directory"] = str(self.options.project_dir.resolve())

        # Create thread
        if self._codex is not None:
            self._thread = self._codex.start_thread(thread_options)

        # Log limitations for chat session features
        if self.options.include_user_settings:
            print("   - Note: Codex SDK does not support user-level settings. Using project settings only.", flush=True)

        if self.options.allowed_tools:
            print("   - Note: Codex SDK uses SandboxMode instead of allowed_tools. Tool allowlist is advisory only.", flush=True)

        # Log hook limitation warning
        if self.options.bash_hook or self.options.compact_hook:
            logger.warning(
                "Codex SDK does not support PreToolUse/PreCompact hooks. "
                "Security relies on Codex's built-in sandboxing."
            )
            print("   - Note: Bash command hooks not available with Codex SDK", flush=True)
            print("   - Security relies on Codex's built-in sandboxing", flush=True)

    async def __aenter__(self) -> "CodexAdapter":
        """Enter async context manager."""
        # Codex SDK doesn't require async context initialization
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit async context manager."""
        # Codex SDK handles cleanup automatically
        pass

    async def query(self, message: str | list[dict[str, Any]]) -> None:
        """
        Store the query for run_streamed.

        Codex SDK combines query and response in run_streamed(),
        so we store the message and process it in receive_events().

        Args:
            message: The prompt text or multimodal content blocks.
        """
        self._pending_message = message

    async def receive_events(self) -> AsyncIterator[AgentEvent]:
        """
        Stream events from Codex agent, translating to unified AgentEvent.

        The Codex SDK emits JSONL events like:
        - thread.started
        - item.started / item.updated / item.completed
        - turn.completed / turn.failed
        """
        if not self._thread:
            yield AgentEvent(
                type=EventType.ERROR,
                content="Thread not initialized",
                is_error=True,
            )
            return

        # Convert message to proper format
        if isinstance(self._pending_message, list):
            # Multimodal input: extract text parts, warn about images
            text_parts: list[str] = []
            has_images = False

            for block in self._pending_message:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        has_images = True

            if has_images:
                print("   - Warning: Codex SDK does not support image attachments, using text only", flush=True)

            input_data = " ".join(text_parts) if text_parts else ""
        else:
            input_data = self._pending_message

        try:
            streamed = await self._thread.run_streamed(input_data)

            async for event in streamed.events:
                event_type = event.get("type", "")

                if event_type == "item.started":
                    item = event.get("item", {})
                    item_type = item.get("type", "")

                    if item_type == "command_execution":
                        yield AgentEvent(
                            type=EventType.TOOL_CALL,
                            tool_name="Bash",
                            tool_input={"command": item.get("command", "")},
                            tool_id=item.get("id"),
                            raw=event,
                        )
                    elif item_type == "mcp_tool_call":
                        yield AgentEvent(
                            type=EventType.TOOL_CALL,
                            tool_name=f"mcp__{item.get('server', '')}__{item.get('tool', '')}",
                            tool_input=item.get("arguments", {}),
                            tool_id=item.get("id"),
                            raw=event,
                        )

                elif event_type == "item.completed":
                    item = event.get("item", {})
                    item_type = item.get("type", "")

                    if item_type == "agent_message":
                        yield AgentEvent(
                            type=EventType.TEXT,
                            content=item.get("text", ""),
                            raw=event,
                        )

                    elif item_type == "command_execution":
                        exit_code = item.get("exit_code", 0)
                        yield AgentEvent(
                            type=EventType.TOOL_RESULT,
                            tool_name="Bash",
                            content=item.get("aggregated_output", ""),
                            tool_id=item.get("id"),
                            is_error=exit_code != 0,
                            raw=event,
                        )

                    elif item_type == "file_change":
                        changes = item.get("changes", [])
                        change_summary = ", ".join(
                            f"{c.get('kind', 'modify')} {c.get('path', '')}"
                            for c in changes
                        )
                        yield AgentEvent(
                            type=EventType.TOOL_RESULT,
                            tool_name="Edit",
                            content=f"File changes: {change_summary}",
                            tool_id=item.get("id"),
                            is_error=item.get("status") == "failed",
                            raw=event,
                        )

                    elif item_type == "mcp_tool_call":
                        result = item.get("result", {})
                        error = item.get("error")
                        content = ""

                        if result:
                            result_content = result.get("content", [])
                            if result_content:
                                content = str(result_content[0].get("text", ""))
                        if error:
                            content = error.get("message", "MCP tool error")

                        yield AgentEvent(
                            type=EventType.TOOL_RESULT,
                            tool_name=f"mcp__{item.get('server', '')}__{item.get('tool', '')}",
                            content=content,
                            tool_id=item.get("id"),
                            is_error=item.get("status") == "failed",
                            raw=event,
                        )

                    elif item_type == "reasoning":
                        # Reasoning is informational, emit as text
                        yield AgentEvent(
                            type=EventType.TEXT,
                            content=f"[Reasoning] {item.get('text', '')}",
                            raw=event,
                        )

                    elif item_type == "error":
                        yield AgentEvent(
                            type=EventType.ERROR,
                            content=item.get("message", "Unknown error"),
                            is_error=True,
                            raw=event,
                        )

                elif event_type == "turn.completed":
                    # Turn complete - emit DONE event
                    yield AgentEvent(type=EventType.DONE, raw=event)

                elif event_type == "turn.failed":
                    error = event.get("error", {})
                    yield AgentEvent(
                        type=EventType.ERROR,
                        content=error.get("message", "Turn failed"),
                        is_error=True,
                        raw=event,
                    )
                    yield AgentEvent(type=EventType.DONE, raw=event)

                elif event_type == "error":
                    yield AgentEvent(
                        type=EventType.ERROR,
                        content=event.get("message", "Stream error"),
                        is_error=True,
                        raw=event,
                    )

        except Exception as e:
            logger.error(f"Codex SDK error: {e}")
            yield AgentEvent(
                type=EventType.ERROR,
                content=str(e),
                is_error=True,
            )
            yield AgentEvent(type=EventType.DONE)

    @property
    def supports_hooks(self) -> bool:
        """Codex SDK does not support blocking hooks."""
        return False
