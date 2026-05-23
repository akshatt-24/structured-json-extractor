"""
tests/test_extraction.py — Integration and unit tests for the extraction pipeline.

Tests that don't require a live API key use mocking.
Tests that do require a key are skipped unless OPENROUTER_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import CustomerSupportTicket, ExtractionMetadata, ExtractionResult
from app.validators import parse_json_string, validate_against_schema
from app.prompts import build_extraction_prompt, build_repair_prompt
from app.utils import pretty_json, truncate, read_file


# ---------------------------------------------------------------------------
# Prompt builder tests (pure functions, no I/O)
# ---------------------------------------------------------------------------


def test_extraction_prompt_contains_text():
    prompt = build_extraction_prompt("Some raw text here.")
    assert "Some raw text here." in prompt
    assert "JSON" in prompt


def test_repair_prompt_contains_malformed():
    prompt = build_repair_prompt('{"broken":')
    assert '{"broken":' in prompt


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------


def test_pretty_json_dict():
    data = {"a": 1, "b": None}
    output = pretty_json(data)
    parsed = json.loads(output)
    assert parsed["a"] == 1
    assert parsed["b"] is None


def test_pretty_json_pydantic_model():
    ticket = CustomerSupportTicket(customer_name="Alice")
    output = pretty_json(ticket)
    parsed = json.loads(output)
    assert parsed["customer_name"] == "Alice"


def test_truncate_short_string():
    assert truncate("hello", 200) == "hello"


def test_truncate_long_string():
    long = "x" * 500
    result = truncate(long, 200)
    assert len(result) <= 201  # 200 chars + ellipsis char
    assert result.endswith("…")


def test_read_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_file("/nonexistent/path/file.txt")


def test_read_file_sample(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    content = read_file(str(f))
    assert content == "hello world"


# ---------------------------------------------------------------------------
# Retry handler tests (mock async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_retries_success_first_attempt():
    """Should return result with 0 retries on first success."""
    from app.retry_handler import run_with_retries

    async def factory():
        return "ok"

    result, retries = await run_with_retries(factory, max_attempts=3)
    assert result == "ok"
    assert retries == 0


@pytest.mark.asyncio
async def test_run_with_retries_fails_then_succeeds():
    """Should succeed on 2nd attempt and report 1 retry."""
    from app.retry_handler import run_with_retries

    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("simulated failure")
        return "success"

    result, retries = await run_with_retries(factory, max_attempts=3, min_wait=0.01)
    assert result == "success"
    assert retries == 1


@pytest.mark.asyncio
async def test_run_with_retries_exhausted():
    """Should raise after all attempts are exhausted."""
    from app.retry_handler import run_with_retries

    async def factory():
        raise ValueError("always fails")

    with pytest.raises(ValueError, match="always fails"):
        await run_with_retries(factory, max_attempts=2, min_wait=0.01)


# ---------------------------------------------------------------------------
# Null field handling
# ---------------------------------------------------------------------------


def test_null_fields_preserved():
    """All-null ticket must serialise with null values, not missing keys."""
    ticket = CustomerSupportTicket()
    dumped = ticket.model_dump()
    for field in [
        "customer_name", "order_id", "product", "issue_type",
        "issue_description", "refund_amount", "priority", "sentiment",
        "confidence_score",
    ]:
        assert field in dumped
        assert dumped[field] is None


# ---------------------------------------------------------------------------
# Mock extraction test (no live API needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_mocked():
    """
    End-to-end extraction test with mocked LLM response.
    Verifies the pipeline builds a correct ExtractionResult.
    """
    mock_ticket = CustomerSupportTicket(
        customer_name="Sarah Johnson",
        order_id="ORD-88271",
        product="Sony WH-1000XM5",
        issue_type="wrong_item",
        issue_description="Customer received wrong product and requests refund.",
        refund_amount=299.99,
        priority="high",
        sentiment="angry",
        confidence_score=0.97,
    )

    with patch("app.extractor._extract_with_model", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_ticket
        mock_fn.side_effect = None

        from app.extractor import extract

        result = await extract(
            "Hi, I ordered Sony headphones ORD-88271 but got the wrong item. "
            "I want a refund of $299.99. — Sarah Johnson"
        )

    assert isinstance(result, ExtractionResult)
    assert result.ticket.customer_name == "Sarah Johnson"
    assert result.ticket.refund_amount == 299.99
    assert result.ticket.sentiment == "angry"
    assert result.metadata.retry_count == 0
    assert result.metadata.repair_applied is False


@pytest.mark.asyncio
async def test_extract_empty_text_raises():
    """Empty text must raise ValueError before hitting the API."""
    from app.extractor import extract

    with pytest.raises(ValueError, match="must not be empty"):
        await extract("   ")