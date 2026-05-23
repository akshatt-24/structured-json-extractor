"""
schemas.py — Pydantic v2 schemas for structured extraction.

Each schema represents a domain object that the LLM should populate.
All fields are Optional to avoid hallucination — unknown values become null.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CustomerSupportTicket(BaseModel):
    """
    Structured representation of a customer support ticket extracted
    from messy, unstructured text (emails, chats, forms, etc.).
    """

    customer_name: Optional[str] = Field(
        default=None,
        description="Full name of the customer. Null if not mentioned.",
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Order or transaction identifier. Null if not mentioned.",
    )
    product: Optional[str] = Field(
        default=None,
        description="Name or description of the product involved. Null if not mentioned.",
    )
    issue_type: Optional[str] = Field(
        default=None,
        description=(
            "Category of the issue: refund, shipping, damaged, wrong_item, "
            "billing, technical, other. Null if not determinable."
        ),
    )
    issue_description: Optional[str] = Field(
        default=None,
        description="Brief factual summary of the customer's complaint or request.",
    )
    refund_amount: Optional[float] = Field(
        default=None,
        description="Monetary refund amount requested or mentioned. Null if absent.",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Inferred priority: low, medium, high, urgent. Null if unclear.",
    )
    sentiment: Optional[str] = Field(
        default=None,
        description=(
            "Customer's emotional tone: positive, neutral, frustrated, angry, "
            "sad. Null if unclear."
        ),
    )
    confidence_score: Optional[float] = Field(
        default=None,
        description=(
            "Overall extraction confidence between 0.0 and 1.0. "
            "Higher means the text was clear and unambiguous."
        ),
        ge=0.0,
        le=1.0,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_name": "Jane Smith",
                "order_id": "ORD-9981",
                "product": "Wireless Headphones",
                "issue_type": "refund",
                "issue_description": "Customer received wrong item and wants a full refund.",
                "refund_amount": 89.99,
                "priority": "high",
                "sentiment": "frustrated",
                "confidence_score": 0.91,
            }
        }
    }


class ExtractionMetadata(BaseModel):
    """Metadata about a single extraction run."""

    processing_time_seconds: float = Field(
        description="Wall-clock time taken for the extraction in seconds."
    )
    retry_count: int = Field(
        description="Number of retries performed (0 = succeeded on first attempt)."
    )
    model_used: str = Field(
        description="Model identifier used for this extraction."
    )
    repair_applied: bool = Field(
        default=False,
        description="True if a JSON repair pass was required.",
    )


class ExtractionResult(BaseModel):
    """
    Complete extraction result combining the structured ticket
    and the metadata about how it was produced.
    """

    ticket: CustomerSupportTicket
    metadata: ExtractionMetadata
