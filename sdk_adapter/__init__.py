"""
SDK Adapter Package
====================

Provides a unified interface for multiple agent SDKs (Claude, Codex).
Use the factory function to create an adapter based on AUTOFORGE_SDK env var.

Usage:
    from sdk_adapter import create_adapter, AdapterOptions

    options = AdapterOptions(model="...", project_dir=Path(...))
    adapter = create_adapter(options)

    async with adapter:
        await adapter.query("Your prompt")
        async for event in adapter.receive_events():
            print(event)
"""

from sdk_adapter.factory import create_adapter, get_sdk_type
from sdk_adapter.protocols import SDKAdapter
from sdk_adapter.types import AdapterOptions, AgentEvent, EventType

__all__ = [
    "create_adapter",
    "get_sdk_type",
    "SDKAdapter",
    "AdapterOptions",
    "AgentEvent",
    "EventType",
]
