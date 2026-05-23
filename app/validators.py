"""
validators.py — Schema validation utilities.

Provides helpers to validate raw dicts/JSON strings against Pydantic schemas
and to detect whether a response looks like valid JSON before parsing.
"""

from __future__ import annotations

import json
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.logger import get_logger

logger = get_logger("validators")

T = TypeVar("T", bound=BaseModel)


class ValidationResult:
    """Holds the outcome of a validation attempt."""

    def __init__(
        self,
        success: bool,
        model: BaseModel | None = None,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.model = model
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return f"ValidationResult(success={self.success}, error={self.error!r})"


def validate_against_schema(
    data: dict[str, Any],
    schema: Type[T],
) -> ValidationResult:
    """
    Validate a parsed dict against a Pydantic schema.

    Args:
        data: Parsed JSON dict.
        schema: Pydantic model class to validate against.

    Returns:
        ValidationResult with success flag and either model or error.
    """
    try:
        instance = schema.model_validate(data)
        logger.debug("Validation passed for schema '%s'.", schema.__name__)
        return ValidationResult(success=True, model=instance)
    except ValidationError as exc:
        error_summary = _summarise_validation_error(exc)
        logger.warning(
            "Validation failed for schema '%s': %s", schema.__name__, error_summary
        )
        return ValidationResult(success=False, error=error_summary)


def parse_json_string(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Attempt to parse a raw string as JSON.

    Strips common model-output artefacts like markdown code fences.

    Args:
        raw: Raw string from the model.

    Returns:
        Tuple of (parsed_dict, error_message).
        parsed_dict is None on failure; error_message is None on success.
    """
    cleaned = _strip_markdown_fences(raw.strip())
    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return None, f"Expected JSON object, got {type(parsed).__name__}"
        return parsed, None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"


def _strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences (```json ... ```) that models sometimes add.

    Args:
        text: Possibly fence-wrapped string.

    Returns:
        Cleaned string.
    """
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        return "\n".join(inner).strip()
    return text


def _summarise_validation_error(exc: ValidationError) -> str:
    """
    Produce a short human-readable summary of a ValidationError.

    Args:
        exc: Pydantic ValidationError instance.

    Returns:
        Single-line string summarising the failures.
    """
    parts = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        msg = error["msg"]
        parts.append(f"{loc}: {msg}")
    return "; ".join(parts)
