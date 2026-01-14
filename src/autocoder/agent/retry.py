from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    initial_delay_s: float = 1.0
    max_delay_s: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    # Longer default for rate limits (429)
    rate_limit_initial_delay_s: float = 30.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def retry_config_from_env(prefix: str = "AUTOCODER_SDK_") -> RetryConfig:
    """
    Env vars:
    - {prefix}MAX_ATTEMPTS (default 3)
    - {prefix}INITIAL_DELAY_S (default 1)
    - {prefix}MAX_DELAY_S (default 60)
    - {prefix}EXPONENTIAL_BASE (default 2)
    - {prefix}JITTER (default true)
    - {prefix}RATE_LIMIT_INITIAL_DELAY_S (default 30)
    """
    jitter_raw = os.environ.get(f"{prefix}JITTER", "true").lower()
    jitter = jitter_raw not in ("0", "false", "no")
    return RetryConfig(
        max_attempts=max(1, _env_int(f"{prefix}MAX_ATTEMPTS", 3)),
        initial_delay_s=max(0.0, _env_float(f"{prefix}INITIAL_DELAY_S", 1.0)),
        max_delay_s=max(0.0, _env_float(f"{prefix}MAX_DELAY_S", 60.0)),
        exponential_base=max(1.0, _env_float(f"{prefix}EXPONENTIAL_BASE", 2.0)),
        jitter=jitter,
        rate_limit_initial_delay_s=max(0.0, _env_float(f"{prefix}RATE_LIMIT_INITIAL_DELAY_S", 30.0)),
    )


def classify_transient_error(exc: Exception) -> Optional[str]:
    msg = str(exc).lower()
    if "rate limit" in msg or "429" in msg:
        return "rate_limit"
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "connection" in msg or "econnreset" in msg or "econnrefused" in msg:
        return "connection"
    return None


def _compute_delay(config: RetryConfig, attempt_index: int, error_type: Optional[str]) -> float:
    # attempt_index starts at 0 for first retry sleep.
    base = config.rate_limit_initial_delay_s if error_type == "rate_limit" else config.initial_delay_s
    delay = base * (config.exponential_base ** attempt_index)
    delay = min(delay, config.max_delay_s)
    if config.jitter and delay > 0:
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
    return max(0.0, delay)


async def execute_with_retry(
    func: Callable[[], Awaitable[T]],
    *,
    config: RetryConfig,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    last: Exception | None = None
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except Exception as e:
            last = e
            if is_retryable is not None and not is_retryable(e):
                raise
            error_type = classify_transient_error(e)
            if error_type is None:
                raise
            if attempt >= config.max_attempts:
                raise
            delay = _compute_delay(config, attempt_index=attempt - 1, error_type=error_type)
            if delay:
                await asyncio.sleep(delay)
    assert last is not None
    raise last


def execute_with_retry_sync(
    func: Callable[[], T],
    *,
    config: RetryConfig,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """
    Synchronous retry/backoff helper for non-async operations.

    Used for subprocess/CLI calls where transient failures (timeouts, rate limits, connection errors)
    should be retried with the same policy as the async SDK retry.
    """
    last: Exception | None = None
    for attempt in range(1, config.max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last = e
            if is_retryable is not None and not is_retryable(e):
                raise
            error_type = classify_transient_error(e)
            if error_type is None:
                raise
            if attempt >= config.max_attempts:
                raise
            delay = _compute_delay(config, attempt_index=attempt - 1, error_type=error_type)
            if delay:
                time.sleep(delay)
    assert last is not None
    raise last

