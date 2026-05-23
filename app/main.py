"""
main.py — FastAPI application factory.

Creates the FastAPI app, mounts the router, and configures lifespan events.
Run with:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api import router
from app.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — runs startup/shutdown logic."""
    logger.info("structured-json-extractor API starting up…")
    yield
    logger.info("structured-json-extractor API shut down.")


app = FastAPI(
    title="Structured JSON Extractor",
    description=(
        "Extract validated structured JSON from messy unstructured text "
        "using an LLM with automatic retry and repair."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="")
