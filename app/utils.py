"""
utils.py — Shared utility helpers used across the project.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Generator


@contextmanager
def timer() -> Generator[dict[str, float], None, None]:
    """
    Context manager that measures elapsed wall-clock time.

    Usage::

        with timer() as t:
            do_something()
        print(t["elapsed"])  # seconds as float
    """
    result: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed"] = round(time.perf_counter() - start, 4)


def pretty_json(obj: Any) -> str:
    """
    Serialise any JSON-serialisable object to an indented string.

    Args:
        obj: Dict, Pydantic model (.model_dump()), or other JSON-compatible object.

    Returns:
        Pretty-printed JSON string.
    """
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    return json.dumps(obj, indent=2, default=str)


def read_file(path: str) -> str:
    """
    Read a text file and return its content.

    Args:
        path: Absolute or relative path to the file.

    Returns:
        File content as string.

    Raises:
        FileNotFoundError: If the path does not exist.
        IOError: On read failure.
    """
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def truncate(text: str, max_chars: int = 200) -> str:
    """
    Truncate a string for safe display in log messages.

    Args:
        text: Input string.
        max_chars: Maximum characters to keep.

    Returns:
        Possibly truncated string with ellipsis.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"
