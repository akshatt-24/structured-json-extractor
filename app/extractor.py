"""
extractor.py — Core LLM extraction engine.

CRITICAL FIX: Every AsyncOpenAI client must include HTTP-Referer and X-Title
headers in default_headers. Without them OpenRouter silently rejects all
requests with 403 at infrastructure level — they never reach the logging
system, so the API key shows "Last Used: Never" permanently.

Other design decisions:
  - max_retries=1 on Instructor calls — disables Instructor's internal retry.
    All retry/back-off/fallback logic is ours.
  - On RateLimitError: cycle through fallback models before waiting.
  - On NotFoundError (404): skip that model immediately, try next fallback.
  - InstructorRetryException is always unwrapped to expose the real cause.
  - JSON repair only for genuine parse/validation failures, never API errors.
"""

from __future__ import annotations

import time
from typing import Any

import instructor
from instructor.exceptions import InstructorRetryException
from openai import (
    AsyncOpenAI,
    RateLimitError,
    APIStatusError,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
)

from app.config import config
from app.logger import get_logger
from app.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    REPAIR_SYSTEM_PROMPT,
    build_extraction_prompt,
    build_repair_prompt,
)
from app.retry_handler import run_with_retries
from app.schemas import CustomerSupportTicket, ExtractionMetadata, ExtractionResult
from app.utils import truncate
from app.validators import parse_json_string, validate_against_schema

logger = get_logger("extractor")

_API_ERRORS = (RateLimitError, APIStatusError, APIConnectionError, APITimeoutError)
_SKIP_MODEL_ERRORS = (NotFoundError,)   # 404 — model gone, skip immediately


def _required_headers() -> dict[str, str]:
    """
    Return headers that OpenRouter requires on every request.

    Without HTTP-Referer / X-Title, OpenRouter rejects requests at the
    CDN/infrastructure layer with 403 "Host not in allowlist" BEFORE they
    reach the logging system — causing "Last Used: Never" on the key page.
    """
    return {
        "HTTP-Referer": config.http_referer,
        "X-Title": config.app_title,
    }


def _build_raw_client() -> AsyncOpenAI:
    """Build a raw AsyncOpenAI client with required OpenRouter headers."""
    return AsyncOpenAI(
        api_key=config.openrouter_api_key,
        base_url=config.base_url,
        default_headers=_required_headers(),
    )


def _build_instructor_client() -> instructor.AsyncInstructor:
    return instructor.from_openai(_build_raw_client(), mode=instructor.Mode.JSON)


_client: instructor.AsyncInstructor | None = None


def get_client() -> instructor.AsyncInstructor:
    global _client
    if _client is None:
        _client = _build_instructor_client()
    return _client


def _unwrap_instructor_exception(exc: Exception) -> Exception:
    """
    Unwrap InstructorRetryException to expose the real underlying exception.
    Chain: InstructorRetryException -> RetryError (__cause__) -> real_exc
    """
    if not isinstance(exc, InstructorRetryException):
        return exc

    checkable = (AuthenticationError, NotFoundError) + _API_ERRORS

    # args[0] is the last exception from instructor's internal tenacity loop
    inner = exc.args[0] if exc.args else None
    if isinstance(inner, checkable):
        return inner

    for attr in ("__cause__", "__context__"):
        cause = getattr(inner, attr, None)
        if isinstance(cause, checkable):
            return cause

    direct = getattr(exc, "__cause__", None)
    if direct is not None:
        for attr in ("__cause__", "__context__"):
            nested = getattr(direct, attr, None)
            if isinstance(nested, checkable):
                return nested
        if isinstance(direct, checkable):
            return direct

    return exc


async def _extract_with_model(raw_text: str, model: str) -> CustomerSupportTicket:
    """
    Single extraction attempt against a specific model.
    max_retries=1 disables Instructor's internal retry loop entirely.
    """
    client = get_client()
    logger.info("Sending extraction request to model '%s'.", model)

    try:
        ticket: CustomerSupportTicket = await client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=1024,
            max_retries=1,
            response_model=CustomerSupportTicket,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_extraction_prompt(raw_text)},
            ],
        )
    except InstructorRetryException as exc:
        raise _unwrap_instructor_exception(exc) from exc

    if ticket is None:
        raise ValueError("Model returned empty response.")

    logger.info("Extraction successful with model '%s'.", model)
    return ticket


async def _repair_json(malformed: str, model: str) -> dict[str, Any]:
    """Send malformed JSON back to the model for syntax repair."""
    logger.warning("Attempting JSON repair with model '%s'.", model)
    raw_client = _build_raw_client()  # fresh client with required headers
    response = await raw_client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": build_repair_prompt(malformed)},
        ],
    )
    repaired_text = response.choices[0].message.content or ""
    parsed, error = parse_json_string(repaired_text)
    if parsed is None:
        raise ValueError(f"Repair failed — still invalid JSON: {error}")
    logger.info("JSON repair succeeded.")
    return parsed


def _looks_like_repairable_json(text: str) -> bool:
    stripped = text.strip()
    if not (stripped.startswith("{") or "```" in stripped):
        return False
    bad_markers = (
        "Error code:", "rate-limited", "retry_after", "RateLimitError",
        "APIStatusError", "Provider returned error", "AuthenticationError",
        "NotFoundError", "No endpoints found",
    )
    return not any(m.lower() in text.lower() for m in bad_markers)


def _get_model_sequence() -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for m in [config.model_name] + config.fallback_models:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


async def extract(raw_text: str) -> ExtractionResult:
    """
    Public extraction entry point.

    Model selection strategy:
      1. Try primary model.
      2. On RateLimitError or NotFoundError → immediately try next fallback.
      3. If all fallbacks exhausted → wait (back-off) and retry from primary.
      4. AuthenticationError → fail immediately with actionable message.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Input text must not be empty.")

    repair_applied = False
    start = time.perf_counter()
    model_sequence = _get_model_sequence()
    skipped_models: set[str] = set()   # permanently skip 404 models
    model_index = 0
    used_model = model_sequence[0]

    def _next_available_model(from_index: int) -> tuple[int, str] | None:
        """Return (index, name) of the next non-skipped model, or None."""
        for i in range(from_index, len(model_sequence)):
            if model_sequence[i] not in skipped_models:
                return i, model_sequence[i]
        return None

    async def _attempt() -> CustomerSupportTicket:
        nonlocal repair_applied, model_index, used_model

        pick = _next_available_model(model_index)
        if pick is None:
            # All models skipped (all returned 404) — reset and try primary again
            skipped_models.clear()
            model_index = 0
            pick = (0, model_sequence[0])

        model_index, current_model = pick
        used_model = current_model

        try:
            return await _extract_with_model(raw_text, current_model)

        except AuthenticationError as exc:
            logger.error(
                "Authentication failed. Your OPENROUTER_API_KEY is invalid or expired.\n"
                "  → Get a valid key at https://openrouter.ai/keys\n"
                "  → Make sure it starts with 'sk-or-v1-'"
            )
            raise RuntimeError(
                "Invalid API key. Set a valid OPENROUTER_API_KEY in your .env file. "
                "Get one free at https://openrouter.ai/keys"
            ) from exc

        except _SKIP_MODEL_ERRORS as exc:
            # 404 — this model no longer has endpoints on OpenRouter
            logger.warning("Model '%s' not found (404) — skipping permanently.", current_model)
            skipped_models.add(current_model)
            # Advance and immediately try the next available model
            next_pick = _next_available_model(model_index + 1)
            if next_pick is not None:
                model_index, next_model = next_pick
                used_model = next_model
                logger.info("Switching to '%s'.", next_model)
                return await _extract_with_model(raw_text, next_model)
            else:
                raise RuntimeError(
                    "All configured models returned 404 (no endpoints). "
                    "Update FALLBACK_MODELS in your .env — "
                    "check https://openrouter.ai/models for active free models."
                ) from exc

        except RateLimitError as exc:
            # Try next fallback immediately; reset index so back-off retry retries all
            next_pick = _next_available_model(model_index + 1)
            if next_pick is not None:
                model_index, next_model = next_pick
                used_model = next_model
                logger.warning(
                    "Model '%s' rate-limited. Switching to '%s'.",
                    current_model, next_model,
                )
                return await _extract_with_model(raw_text, next_model)
            else:
                logger.warning("All models rate-limited. Will wait and retry.")
                model_index = 0  # reset for next retry cycle
                raise

        except _API_ERRORS as exc:
            logger.warning("API error (%s). Will retry.", type(exc).__name__)
            raise

        except Exception as exc:
            raw_response = str(exc)
            if _looks_like_repairable_json(raw_response):
                try:
                    repaired_dict = await _repair_json(raw_response, current_model)
                    result = validate_against_schema(repaired_dict, CustomerSupportTicket)
                    if result.success:
                        repair_applied = True
                        return result.model  # type: ignore[return-value]
                    raise ValueError(f"Post-repair validation failed: {result.error}")
                except _API_ERRORS:
                    raise
            raise

    ticket, retry_count = await run_with_retries(
        coro_factory=_attempt,
        max_attempts=config.max_retries,
        min_wait=2.0,
        max_wait=35.0,
    )

    elapsed = round(time.perf_counter() - start, 4)
    metadata = ExtractionMetadata(
        processing_time_seconds=elapsed,
        retry_count=retry_count,
        model_used=used_model,
        repair_applied=repair_applied,
    )
    logger.info(
        "Extraction complete in %.3fs | model=%s | retries=%d | repair=%s",
        elapsed, used_model, retry_count, repair_applied,
    )
    return ExtractionResult(ticket=ticket, metadata=metadata)