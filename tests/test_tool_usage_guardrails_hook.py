import asyncio

from autocoder.agent.hooks import ToolUsageGuardrails


def test_tool_usage_guardrails_blocks_after_max_calls(monkeypatch):
    monkeypatch.setenv("AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS", "2")
    g = ToolUsageGuardrails.from_env()

    payload = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    assert asyncio.run(g.pre_tool_use(payload)) == {}
    assert asyncio.run(g.pre_tool_use(payload)) == {}
    out = asyncio.run(g.pre_tool_use(payload))
    assert out.get("decision") == "block"
    assert "too many tool calls" in (out.get("reason") or "").lower()


def test_tool_usage_guardrails_blocks_repeated_identical_calls(monkeypatch):
    monkeypatch.setenv("AUTOCODER_GUARDRAIL_MAX_SAME_TOOL_CALLS", "2")
    g = ToolUsageGuardrails.from_env()

    payload = {"tool_name": "Read", "tool_input": {"file_path": "x.txt"}}
    assert asyncio.run(g.pre_tool_use(payload)) == {}
    assert asyncio.run(g.pre_tool_use(payload)) == {}
    out = asyncio.run(g.pre_tool_use(payload))
    assert out.get("decision") == "block"
    assert "repeated identical tool call" in (out.get("reason") or "").lower()

