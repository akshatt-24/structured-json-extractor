"""
retry_handler.py — Async retry with Retry-After awareness.

Reads retry_after_seconds from OpenRouter 429 responses so the back-off
waits exactly as long as the provider requests rather than guessing.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from app.logger import get_logger

logger = get_logger("retry_handler")

F = TypeVar("F")


def _extract_retry_after(exc: Exception) -> float | None:
    """
    Read the retry_after_seconds hint from an OpenRouter RateLimitError.

    OpenRouter body structure:
      {'error': {'metadata': {'retry_after_seconds': 29, ...}}}

    The openai SDK stores the parsed body in exc.body.

    Returns:
        Seconds to wait, or None if not available.
    """
    try:
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            retry_after = body.get("error", {}).get("metadata", {}).get("retry_after_seconds")
            if retry_after is not None:
                return float(retry_after)

        response = getattr(exc, "response", None)
        if response is not None:
            header = getattr(response, "headers", {}).get("Retry-After")
            if header is not None:
                return float(header)
    except Exception:  # noqa: BLE001
        pass
    return None


async def run_with_retries(
    coro_factory: Callable[[], Coroutine[Any, Any, F]],
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 35.0,
) -> tuple[F, int]:
    """
    Run an async coroutine factory with retry logic.

    Honours the provider's retry_after_seconds on 429s.  Falls back to
    exponential back-off when no hint is available.

    Returns:
        (result, retries_performed)  — retries_performed is 0 on first success.

    Raises:
        Last exception if all attempts are exhausted.
    """
    retries = 0
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await coro_factory()
            return result, retries

        except Exception as exc:  # noqa: BLE001
            last_exc = exc

            if attempt >= max_attempts:
                logger.error(
                    "All %d attempts exhausted. Final error: %s: %s",
                    max_attempts, type(exc).__name__, exc,
                )
                break

            retries += 1
            suggested = _extract_retry_after(exc)

            if suggested is not None:
                wait_time = min(suggested + 1.0, max_wait)
                logger.warning(
                    "Attempt %d/%d — rate limited. Waiting %.0fs (provider requested %.0fs)…",
                    attempt, max_attempts, wait_time, suggested,
                )
            else:
                wait_time = min(min_wait * (2 ** (attempt - 1)), max_wait)
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                    attempt, max_attempts, type(exc).__name__, wait_time,
                )

            await asyncio.sleep(wait_time)

    raise last_exc  # type: ignore[misc]