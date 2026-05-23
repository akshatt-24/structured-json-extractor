"""
config.py — Centralised configuration loader.

Critical: OpenRouter requires HTTP-Referer and X-Title headers on every
request, or requests are silently rejected at the infrastructure level
(403 "Host not in allowlist") before they reach the logging system.
These headers are stored here and applied in every client build.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    openrouter_api_key: str
    model_name: str
    fallback_models: list[str]
    max_retries: int
    log_level: str
    base_url: str = field(default="https://openrouter.ai/api/v1")
    # Required by OpenRouter — without these every request gets 403
    # and is never logged ("Last Used: Never" on the key page)
    http_referer: str = field(default="http://localhost:8000")
    app_title: str = field(default="structured-json-extractor")

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY is not set. "
                "Copy .env.example to .env and add your key from "
                "https://openrouter.ai/keys"
            )

        primary = os.getenv("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct:free")

        fallback_env = os.getenv("FALLBACK_MODELS", "")
        if fallback_env.strip():
            fallbacks = [m.strip() for m in fallback_env.split(",") if m.strip()]
        else:
            # Verified active free models on OpenRouter (May 2026)
            # mistralai/mistral-7b-instruct:free was removed — do NOT use it
            fallbacks = [
                "meta-llama/llama-3.1-8b-instruct:free",
                "google/gemma-2-9b-it:free",
                "qwen/qwen-2.5-7b-instruct:free",
                "deepseek/deepseek-r1-0528:free",
            ]

        return cls(
            openrouter_api_key=api_key,
            model_name=primary,
            fallback_models=fallbacks,
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            http_referer=os.getenv("HTTP_REFERER", "http://localhost:8000"),
            app_title=os.getenv("APP_TITLE", "structured-json-extractor"),
        )


config = Config.from_env()