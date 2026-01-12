import asyncio

from autocoder.agent.agent import run_agent_session


class TextBlock:
    def __init__(self, text: str):
        self.text = text


class ToolUseBlock:
    def __init__(self, name: str, input: dict | None = None):
        self.name = name
        self.input = input or {}


class ToolResultBlock:
    def __init__(self, content: str, is_error: bool = False):
        self.content = content
        self.is_error = is_error


class AssistantMessage:
    def __init__(self, content):
        self.content = content


class UserMessage:
    def __init__(self, content):
        self.content = content


class _FakeClient:
    def __init__(self, messages):
        self._messages = messages

    async def query(self, _message: str) -> None:
        return None

    async def receive_response(self):
        for m in self._messages:
            yield m


def test_guardrail_max_tool_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS", "2")

    messages = [
        AssistantMessage([ToolUseBlock("Bash"), ToolUseBlock("Bash"), ToolUseBlock("Bash")]),
    ]
    client = _FakeClient(messages)
    status, resp = asyncio.run(run_agent_session(client, "hi", tmp_path))
    assert status == "error"
    assert "too many tool calls" in resp.lower()


def test_guardrail_max_consecutive_tool_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCODER_GUARDRAIL_MAX_CONSECUTIVE_TOOL_ERRORS", "1")

    messages = [
        UserMessage([ToolResultBlock("fail1", is_error=True)]),
        UserMessage([ToolResultBlock("fail2", is_error=True)]),
    ]
    client = _FakeClient(messages)
    status, resp = asyncio.run(run_agent_session(client, "hi", tmp_path))
    assert status == "error"
    assert "consecutive tool errors" in resp.lower()
