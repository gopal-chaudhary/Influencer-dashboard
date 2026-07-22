"""Configuration for the Gemini integration.

This module keeps the AI provider settings in one place so the AI service stays
focused on prompting, retrying, and parsing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_OUTPUT_TOKENS = 600
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INITIAL_DELAY_SECONDS = 1.0
DEFAULT_RETRY_MAX_DELAY_SECONDS = 8.0

ENV_API_KEY = "GEMINI_API_KEY"
ENV_MODEL = "GEMINI_MODEL"
ENV_TEMPERATURE = "GEMINI_TEMPERATURE"
ENV_MAX_OUTPUT_TOKENS = "GEMINI_MAX_OUTPUT_TOKENS"
ENV_TIMEOUT_SECONDS = "GEMINI_TIMEOUT_SECONDS"
ENV_MAX_RETRIES = "GEMINI_MAX_RETRIES"
ENV_RETRY_INITIAL_DELAY_SECONDS = "GEMINI_RETRY_INITIAL_DELAY_SECONDS"
ENV_RETRY_MAX_DELAY_SECONDS = "GEMINI_RETRY_MAX_DELAY_SECONDS"


@dataclass(frozen=True, slots=True)
class GrokConfig:
    """Store Gemini connection settings and retry behavior.

    The class name is preserved for compatibility with the existing architecture
    and imports, but the configuration is now entirely Gemini-based.
    """

    api_key: str | None
    model: str = DEFAULT_GEMINI_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_initial_delay_seconds: float = DEFAULT_RETRY_INITIAL_DELAY_SECONDS
    retry_max_delay_seconds: float = DEFAULT_RETRY_MAX_DELAY_SECONDS

    @classmethod
    def from_env(cls) -> "GrokConfig":
        """Load configuration from environment variables and ``.env`` files."""
        load_dotenv()
        return cls(
            api_key=os.getenv(ENV_API_KEY),
            model=os.getenv(ENV_MODEL, DEFAULT_GEMINI_MODEL),
            temperature=_read_float(ENV_TEMPERATURE, DEFAULT_TEMPERATURE),
            max_output_tokens=_read_int(ENV_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS),
            timeout_seconds=_read_float(ENV_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS),
            max_retries=_read_int(ENV_MAX_RETRIES, DEFAULT_MAX_RETRIES),
            retry_initial_delay_seconds=_read_float(
                ENV_RETRY_INITIAL_DELAY_SECONDS,
                DEFAULT_RETRY_INITIAL_DELAY_SECONDS,
            ),
            retry_max_delay_seconds=_read_float(
                ENV_RETRY_MAX_DELAY_SECONDS,
                DEFAULT_RETRY_MAX_DELAY_SECONDS,
            ),
        )

    def __post_init__(self) -> None:
        """Normalize and validate configuration values."""
        object.__setattr__(self, "api_key", _normalize_optional_text(self.api_key))
        object.__setattr__(self, "model", self.model.strip())

        if not self.model:
            raise ValueError("model cannot be empty")
        if self.temperature < 0:
            raise ValueError("temperature cannot be negative")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.max_retries <= 0:
            raise ValueError("max_retries must be greater than zero")
        if self.retry_initial_delay_seconds < 0:
            raise ValueError("retry_initial_delay_seconds cannot be negative")
        if self.retry_max_delay_seconds <= 0:
            raise ValueError("retry_max_delay_seconds must be greater than zero")
        if self.retry_initial_delay_seconds > self.retry_max_delay_seconds:
            raise ValueError("retry_initial_delay_seconds cannot exceed retry_max_delay_seconds")

    @property
    def has_api_key(self) -> bool:
        """Return ``True`` when an API key is configured."""
        return bool(self.api_key)


def _read_int(name: str, default: int) -> int:
    """Read an integer environment variable with a safe fallback."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def _read_float(name: str, default: float) -> float:
    """Read a float environment variable with a safe fallback."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value.strip())


def _normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text values and convert blanks to ``None``."""
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value or None
