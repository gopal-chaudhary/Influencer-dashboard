"""Reusable service for analyzing influencers with xAI Grok.

The service is kept independent of Streamlit so it can be reused by the UI,
background jobs, tests, or future API endpoints.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
    UnprocessableEntityError,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.grok_config import GrokConfig
from models import AIAnalysis, Influencer


class GrokServiceError(Exception):
    """Base class for Grok service errors."""


class GrokConfigurationError(GrokServiceError):
    """Raised when the Grok service is missing required configuration."""


class GrokResponseParseError(GrokServiceError):
    """Raised when the Grok response cannot be parsed as valid JSON."""


class GrokAPIRequestError(GrokServiceError):
    """Raised when Grok returns an API or transport error after retries."""


@dataclass(slots=True)
class GrokService:
    """Analyze influencer profiles using xAI's OpenAI-compatible API."""

    config: GrokConfig | None = None
    client: OpenAI | None = None

    def __post_init__(self) -> None:
        """Load configuration and build a client if needed."""
        config = self.config or GrokConfig.from_env()
        self.config = config

        if not config.has_api_key:
            raise GrokConfigurationError("Missing xAI API key. Set XAI_API_KEY in the .env file.")

        if self.client is None:
            self.client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
            )

    def analyze_influencer(self, influencer: Influencer) -> AIAnalysis:
        """Analyze one influencer profile and return structured AI insights."""
        prompt = self._build_prompt(influencer)
        response_text = self._execute_request(prompt)
        try:
            return AIAnalysis.from_json(response_text)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise GrokResponseParseError(
                "Grok returned invalid JSON for the influencer analysis"
            ) from exc

    def _execute_request(self, prompt: str) -> str:
        """Execute the model call with retries for transient failures."""
        config = self.config
        assert config is not None
        retryable_exceptions = self._retryable_exceptions()
        retrying = Retrying(
            stop=stop_after_attempt(config.max_retries),
            wait=wait_exponential(
                multiplier=config.retry_initial_delay_seconds,
                min=config.retry_initial_delay_seconds,
                max=config.retry_max_delay_seconds,
            ),
            retry=retry_if_exception_type(retryable_exceptions),
            reraise=True,
        )

        try:
            for attempt in retrying:
                with attempt:
                    return self._create_completion(prompt)
        except (AuthenticationError, BadRequestError, ConflictError, UnprocessableEntityError) as exc:
            raise GrokAPIRequestError(self._format_error_message(exc)) from exc
        except OpenAIError as exc:
            raise GrokAPIRequestError(self._format_error_message(exc)) from exc

        raise GrokAPIRequestError("Grok request failed without a response")

    def _create_completion(self, prompt: str) -> str:
        """Make the actual API request and return the raw assistant content."""
        assert self.client is not None
        config = self.config
        assert config is not None
        response = self.client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an analyst for an influencer discovery system. "
                        "Return JSON only. Do not include markdown, explanations, or code fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise GrokResponseParseError("Grok returned an empty response")
        return content

    def _build_prompt(self, influencer: Influencer) -> str:
        """Build a prompt that asks for structured JSON analysis only."""
        recent_content = "\n".join(f"- {item}" for item in influencer.recent_content) or "- none"
        return (
            "Analyze the following influencer profile and return a single JSON object only.\n\n"
            "Required JSON keys:\n"
            "- detected_language: string\n"
            "- niche: string\n"
            "- government_support_score: integer from 0 to 100\n"
            "- political_orientation: string\n"
            "- confidence: number from 0 to 1\n"
            "- summary: string\n"
            "- keywords: array of short strings\n"
            "- reasoning: string\n\n"
            "Analysis instructions:\n"
            "- Use the bio, recent content, and language fields.\n"
            "- Identify the main niche.\n"
            "- Assess whether the content appears supportive of government initiatives.\n"
            "- Provide a confidence score for your analysis.\n"
            "- If information is unclear, use the best-supported inference rather than fabricating facts.\n"
            "- Return JSON only. No markdown, no prose outside JSON.\n\n"
            f"Name: {influencer.name}\n"
            f"Handle: @{influencer.handle}\n"
            f"Platform: {influencer.platform}\n"
            f"Language: {influencer.language or 'unknown'}\n"
            f"Bio: {influencer.bio or 'none'}\n"
            f"Recent content:\n{recent_content}\n"
            f"Followers: {influencer.followers}\n"
        )

    @staticmethod
    def _retryable_exceptions() -> tuple[type[BaseException], ...]:
        """Return exception types that should be retried."""
        return (
            APIConnectionError,
            APIError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )

    @staticmethod
    def _format_error_message(error: BaseException) -> str:
        """Create a consistent, user-facing error message."""
        return f"Grok request failed: {error}"
