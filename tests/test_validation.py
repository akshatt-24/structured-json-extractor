"""
tests/test_validation.py — Unit tests for schema validation and JSON parsing.
"""

from __future__ import annotations

import json
import pytest

from app.schemas import CustomerSupportTicket, ExtractionMetadata, ExtractionResult
from app.validators import parse_json_string, validate_against_schema


# ---------------------------------------------------------------------------
# parse_json_string tests
# ---------------------------------------------------------------------------


def test_parse_valid_json():
    raw = '{"customer_name": "Alice", "order_id": "ORD-001"}'
    parsed, err = parse_json_string(raw)
    assert parsed is not None
    assert err is None
    assert parsed["customer_name"] == "Alice"


def test_parse_json_with_markdown_fence():
    raw = '```json\n{"customer_name": "Bob"}\n```'
    parsed, err = parse_json_string(raw)
    assert parsed is not None
    assert err is None
    assert parsed["customer_name"] == "Bob"


def test_parse_invalid_json():
    raw = '{"broken": json here'
    parsed, err = parse_json_string(raw)
    assert parsed is None
    assert err is not None
    assert "JSON parse error" in err


def test_parse_non_object_json():
    raw = '["a", "b", "c"]'
    parsed, err = parse_json_string(raw)
    assert parsed is None
    assert err is not None


def test_parse_empty_string():
    parsed, err = parse_json_string("")
    assert parsed is None
    assert err is not None


# ---------------------------------------------------------------------------
# validate_against_schema tests
# ---------------------------------------------------------------------------


def test_validation_success_all_fields():
    data = {
        "customer_name": "Jane Smith",
        "order_id": "ORD-9981",
        "product": "Wireless Headphones",
        "issue_type": "refund",
        "issue_description": "Wrong item received.",
        "refund_amount": 89.99,
        "priority": "high",
        "sentiment": "frustrated",
        "confidence_score": 0.95,
    }
    result = validate_against_schema(data, CustomerSupportTicket)
    assert result.success is True
    assert result.model is not None
    assert result.model.customer_name == "Jane Smith"
    assert result.model.refund_amount == 89.99


def test_validation_success_all_nulls():
    """Schema must accept all-null payload (optional fields)."""
    data = {
        "customer_name": None,
        "order_id": None,
        "product": None,
        "issue_type": None,
        "issue_description": None,
        "refund_amount": None,
        "priority": None,
        "sentiment": None,
        "confidence_score": None,
    }
    result = validate_against_schema(data, CustomerSupportTicket)
    assert result.success is True


def test_validation_success_empty_dict():
    """Empty dict should work because all fields are Optional with defaults."""
    result = validate_against_schema({}, CustomerSupportTicket)
    assert result.success is True
    assert result.model.customer_name is None  # type: ignore


def test_validation_confidence_score_out_of_range():
    """confidence_score must be between 0 and 1."""
    data = {"confidence_score": 1.5}
    result = validate_against_schema(data, CustomerSupportTicket)
    assert result.success is False
    assert result.error is not None


def test_validation_refund_amount_type_coercion():
    """Pydantic v2 should coerce a string numeric to float."""
    data = {"refund_amount": "49.99"}
    result = validate_against_schema(data, CustomerSupportTicket)
    assert result.success is True
    assert result.model.refund_amount == 49.99  # type: ignore


def test_validation_failure_bad_type():
    """refund_amount cannot be a non-numeric string."""
    data = {"refund_amount": "not-a-number"}
    result = validate_against_schema(data, CustomerSupportTicket)
    assert result.success is False


# ---------------------------------------------------------------------------
# ExtractionResult schema tests
# ---------------------------------------------------------------------------


def test_extraction_result_serialisation():
    ticket = CustomerSupportTicket(
        customer_name="Test User",
        order_id="ORD-XYZ",
        refund_amount=19.99,
    )
    meta = ExtractionMetadata(
        processing_time_seconds=0.512,
        retry_count=0,
        model_used="meta-llama/llama-3.3-70b-instruct:free",
        repair_applied=False,
    )
    result = ExtractionResult(ticket=ticket, metadata=meta)
    dumped = result.model_dump()

    assert dumped["ticket"]["customer_name"] == "Test User"
    assert dumped["metadata"]["retry_count"] == 0
    # Should be JSON-serialisable
    assert json.dumps(dumped)
