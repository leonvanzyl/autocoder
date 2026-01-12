import asyncio

from autocoder.agent.retry import execute_with_retry, retry_config_from_env


def test_execute_with_retry_retries_on_429(monkeypatch):
    monkeypatch.setenv("AUTOCODER_SDK_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("AUTOCODER_SDK_INITIAL_DELAY_S", "0")
    monkeypatch.setenv("AUTOCODER_SDK_RATE_LIMIT_INITIAL_DELAY_S", "0")

    calls = {"n": 0}

    async def func():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("429 rate limit")
        return "ok"

    cfg = retry_config_from_env()
    result = asyncio.run(execute_with_retry(func, config=cfg))
    assert result == "ok"
    assert calls["n"] == 2

