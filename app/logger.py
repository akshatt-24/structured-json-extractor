"""
logger.py — Structured logging with rotating file handlers.

Console output is kept clean: only INFO+ from the extractor namespace.
The instructor and openai libraries' internal debug/warning noise is suppressed.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_logger(name: str = "extractor") -> logging.Logger:
    """
    Return a named logger with Rich console + rotating file handler.

    Third-party library loggers (instructor, openai, httpx) are silenced
    so they don't pollute the console.
    """
    # Silence noisy third-party loggers
    for noisy in ("instructor", "openai", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler — clean Rich output
    console_handler = RichHandler(
        rich_tracebacks=False,
        markup=True,
        show_path=False,
        show_time=True,
    )
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Rotating file handler — full DEBUG detail
    file_handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "extractor.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger


logger = get_logger("extractor")