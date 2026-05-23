"""
api.py — FastAPI router with /extract and /health endpoints.

This module defines only the router; it is mounted in main.py.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.extractor import extract
from app.logger import get_logger
from app.schemas import ExtractionResult

logger = get_logger("api")

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models for the API layer
# ---------------------------------------------------------------------------


class ExtractRequest(BaseModel):
    """Request body for POST /extract."""

    text: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": (
                    "Hi, my name is Sarah and I ordered headphones (order #ORD-1234) "
                    "last week. They arrived broken and I want a full refund of $89.99. "
                    "This is really frustrating!"
                )
            }
        }
    }


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/extract",
    response_model=ExtractionResult,
    summary="Extract structured data from raw text",
    description=(
        "Accepts messy unstructured text and returns a validated "
        "CustomerSupportTicket JSON object with extraction metadata."
    ),
)
async def extract_endpoint(request: ExtractRequest) -> ExtractionResult:
    """
    POST /extract

    Args:
        request: JSON body containing the raw text.

    Returns:
        ExtractionResult with ticket and metadata.

    Raises:
        422: If input text is empty.
        500: If extraction fails after all retries.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'text' must not be empty.",
        )

    logger.info("POST /extract — text length=%d chars", len(request.text))

    try:
        result = await extract(request.text)
    except Exception as exc:
        logger.error("Extraction pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        ) from exc

    return result


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """
    GET /health

    Returns a simple status payload to confirm the server is running.
    """
    return HealthResponse(status="healthy")
