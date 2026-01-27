"""
Lightweight Gemini API client (OpenAI-compatible endpoint).

Uses Google's OpenAI-compatible Gemini endpoint:
https://generativelanguage.googleapis.com/v1beta/openai

Environment variables:
- GEMINI_API_KEY   (required)
- GEMINI_MODEL     (optional, default: gemini-1.5-flash)
- GEMINI_BASE_URL  (optional, default: official OpenAI-compatible endpoint)
"""

import os
from typing import AsyncGenerator, Iterable, Optional

from openai import AsyncOpenAI

# Default OpenAI-compatible base URL for Gemini
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def is_gemini_configured() -> bool:
    """Return True if a Gemini API key is available."""
    return bool(os.getenv("GEMINI_API_KEY"))


def _build_client() -> AsyncOpenAI:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    base_url = os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL)
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def stream_chat(
    user_message: str,
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    extra_messages: Optional[Iterable[dict]] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion from Gemini.

    Args:
        user_message: Primary user input
        system_prompt: Optional system prompt to prepend
        model: Optional model name; defaults to GEMINI_MODEL env or fallback constant
        extra_messages: Optional prior messages (list of {"role","content"})
    Yields:
        Text chunks as they arrive.
    """
    client = _build_client()
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if extra_messages:
        messages.extend(extra_messages)

    messages.append({"role": "user", "content": user_message})

    completion = await client.chat.completions.create(
        model=model or DEFAULT_GEMINI_MODEL,
        messages=messages,
        stream=True,
    )

    async for chunk in completion:
        for choice in chunk.choices:
            delta = choice.delta
            if delta and delta.content:
                # delta.content is a list of content parts
                for part in delta.content:
                    text = getattr(part, "text", None) or part.get("text") if isinstance(part, dict) else None
                    if text:
                        yield text
