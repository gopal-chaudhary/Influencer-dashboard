"""Configuration for the xAI Grok integration.

The project keeps all Grok-specific environment and retry settings in one place
so the service stays focused on orchestration and parsing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_XAI_MODEL = "grok-4-latest"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 600
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INITIAL_DELAY_SECONDS = 1.0
DEFAULT_RETRY_MAX_DELAY_SECONDS = 8.0

ENV_API_KEY = "XAI_API_KEY"
ENV_BASE_URL = "XAI_BASE_URL"
ENV_MODEL = "XAI_MODEL"
ENV_MODEL_CANDIDATES = "XAI_MODEL_CANDIDATES"
ENV_TEMPERATURE = "XAI_TEMPERATURE"
ENV_MAX_TOKENS = "XAI_MAX_TOKENS"
ENV_TIMEOUT_SECONDS = "XAI_TIMEOUT_SECONDS"
ENV_MAX_RETRIES = "XAI_MAX_RETRIES"
ENV_RETRY_INITIAL_DELAY_SECONDS = "XAI_RETRY_INITIAL_DELAY_SECONDS"
ENV_RETRY_MAX_DELAY_SECONDS = "XAI_RETRY_MAX_DELAY_SECONDS"


@dataclass(frozen=True, slots=True)
class GrokConfig:
    """Store xAI connection settings and retry behavior."""

    api_key: str | None
    base_url: str = DEFAULT_XAI_BASE_URL
    model: str = DEFAULT_XAI_MODEL
    model_candidates: tuple[str, ...] = ()
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
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
            base_url=os.getenv(ENV_BASE_URL, DEFAULT_XAI_BASE_URL),
            model=os.getenv(ENV_MODEL, DEFAULT_XAI_MODEL),
            model_candidates=_read_model_candidates(os.getenv(ENV_MODEL_CANDIDATES)),
            temperature=_read_float(ENV_TEMPERATURE, DEFAULT_TEMPERATURE),
            max_tokens=_read_int(ENV_MAX_TOKENS, DEFAULT_MAX_TOKENS),
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
        """Normalize values and validate the configuration."""
        object.__setattr__(self, "api_key", _normalize_optional_text(self.api_key))
        object.__setattr__(self, "base_url", self.base_url.strip())
        object.__setattr__(self, "model", self.model.strip())
        normalized_candidates = self._normalize_candidates(self.model_candidates)
        if self.model not in normalized_candidates:
            normalized_candidates = (self.model, *normalized_candidates)
        object.__setattr__(self, "model_candidates", normalized_candidates)

        if not self.base_url:
            raise ValueError("base_url cannot be empty")
        if not self.model:
            raise ValueError("model cannot be empty")
        if self.temperature < 0:
            raise ValueError("temperature cannot be negative")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")
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

    @staticmethod
    def _normalize_candidates(candidates: tuple[str, ...]) -> tuple[str, ...]:
        """Ensure model candidates are unique, ordered, and non-empty."""
        unique_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            cleaned_candidate = candidate.strip()
            if not cleaned_candidate or cleaned_candidate in seen:
                continue
            seen.add(cleaned_candidate)
            unique_candidates.append(cleaned_candidate)
        return tuple(unique_candidates)


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


def _read_model_candidates(value: str | None) -> tuple[str, ...]:
    """Read a comma-separated list of fallback model candidates."""
    default_candidates = ("grok-4-latest", "grok-3-latest", "grok-2-latest")
    if value is None or not value.strip():
        return default_candidates

    parsed_candidates = tuple(part.strip() for part in value.split(",") if part.strip())
    return parsed_candidates or default_candidates


def _normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text values and convert blanks to ``None``."""
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value or None
