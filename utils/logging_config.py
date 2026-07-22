"""Application logging helpers.

The dashboard is mostly a Streamlit app, but the services and workflow benefit
from standard Python logging so production issues can be diagnosed without
changing the UI layer.
"""

from __future__ import annotations

import logging
import os
import sys

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | int | None = None) -> None:
    """Configure the root logger once for the application.

    The function is safe to call multiple times. If handlers already exist, it
    only updates the logging level; otherwise it initializes a standard stdout
    handler.
    """
    resolved_level = _resolve_level(level)
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(resolved_level)
        return

    logging.basicConfig(
        level=resolved_level,
        format=DEFAULT_LOG_FORMAT,
        stream=sys.stdout,
    )
    logging.captureWarnings(True)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for the given module or component."""
    return logging.getLogger(name)


def _resolve_level(level: str | int | None) -> int:
    """Normalize a logging level from a string, integer, or environment value."""
    if level is None:
        level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)

    if isinstance(level, int):
        return level

    normalized_level = str(level).strip().upper()
    resolved_level = logging.getLevelName(normalized_level)
    if isinstance(resolved_level, int):
        return resolved_level

    return logging.INFO
