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
from utils import get_logger


logger = get_logger(__name__)


class GrokServiceError(Exception):
    """Base class for Grok service errors."""


class GrokConfigurationError(GrokServiceError):
    """Raised when the Grok service is missing required configuration."""


class GrokResponseParseError(GrokServiceError):
    """Raised when the Grok response cannot be parsed as valid JSON."""


class GrokAPIRequestError(GrokServiceError):
    """Raised when Grok returns an API or transport error after retries."""


class GrokModelNotFoundError(GrokAPIRequestError):
    """Raised when a configured Grok model cannot be found."""


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
            logger.error("Missing xAI API key in Grok configuration")
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
        logger.debug("Analyzing influencer '%s' with Grok", influencer.handle)

        last_model_error: GrokModelNotFoundError | None = None
        for model_name in self._model_candidates():
            try:
                response_text = self._execute_request(prompt, model_name)
                analysis = AIAnalysis.from_json(response_text)
                logger.debug("Grok analysis completed for '%s' using model '%s'", influencer.handle, model_name)
                return analysis
            except GrokModelNotFoundError as exc:
                last_model_error = exc
                logger.warning(
                    "Grok model '%s' not found for '%s'; trying next candidate",
                    model_name,
                    influencer.handle,
                )
                continue
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.exception("Failed to parse Grok JSON response for '%s'", influencer.handle)
                raise GrokResponseParseError(
                    "Grok returned invalid JSON for the influencer analysis"
                ) from exc

        if last_model_error is not None:
            raise GrokAPIRequestError(
                "No configured Grok model was available. "
                f"Tried: {', '.join(self._model_candidates())}."
            ) from last_model_error

        raise GrokAPIRequestError("Grok request failed without a response")

    def _execute_request(self, prompt: str, model_name: str) -> str:
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
                    return self._create_completion(prompt, model_name)
        except (AuthenticationError, ConflictError, UnprocessableEntityError) as exc:
            logger.error("Non-retryable Grok API error: %s", exc)
            raise GrokAPIRequestError(self._format_error_message(exc)) from exc
        except BadRequestError as exc:
            if self._is_model_not_found_error(exc):
                raise GrokModelNotFoundError(self._format_error_message(exc)) from exc
            logger.error("Grok bad request: %s", exc)
            raise GrokAPIRequestError(self._format_error_message(exc)) from exc
        except OpenAIError as exc:
            logger.error("Grok request failed after retries: %s", exc)
            raise GrokAPIRequestError(self._format_error_message(exc)) from exc

        raise GrokAPIRequestError("Grok request failed without a response")

    def _create_completion(self, prompt: str, model_name: str) -> str:
        """Make the actual API request and return the raw assistant content."""
        assert self.client is not None
        config = self.config
        assert config is not None
        response = self.client.chat.completions.create(
            model=model_name,
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
            logger.warning("Grok returned an empty response")
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

    def _model_candidates(self) -> tuple[str, ...]:
        """Return the configured model followed by fallbacks."""
        config = self.config
        assert config is not None
        return config.model_candidates or (config.model,)

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
    def _is_model_not_found_error(error: BadRequestError) -> bool:
        """Detect the model-not-found case from the OpenAI error payload."""
        error_text = str(error).lower()
        return "model not found" in error_text or "invalid-argument" in error_text

    @staticmethod
    def _format_error_message(error: BaseException) -> str:
        """Create a consistent, user-facing error message."""
        return f"Grok request failed: {error}"
