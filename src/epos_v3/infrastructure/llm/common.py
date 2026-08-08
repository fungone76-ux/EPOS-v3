"""Shared helpers for asynchronous LLM adapters."""
from __future__ import annotations
import asyncio
import json
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_async(operation: Callable[[], Awaitable[T]], retries: int = 3, timeout: float = 120.0) -> T:
    """Run an async operation with timeout and exponential backoff."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout)
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                await asyncio.sleep(2**attempt)
    assert last is not None
    raise last


def json_content(response_json: dict[str, object]) -> dict[str, object]:
    """Extract a JSON object from an OpenAI-style response."""
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("Invalid LLM choice")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("Invalid LLM message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("LLM content is not text")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON must be an object")
    return parsed
