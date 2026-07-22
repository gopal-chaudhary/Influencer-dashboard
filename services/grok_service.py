"""Reusable service for analyzing influencers with Google Gemini.

The service keeps the same public interface as the previous AI integration so
the rest of the architecture remains unchanged.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.grok_config import GrokConfig
from models import AIAnalysis, Influencer
from utils import get_logger


logger = get_logger(__name__)


class GrokServiceError(Exception):
    """Base class for AI service errors."""


class GrokConfigurationError(GrokServiceError):
    """Raised when the AI service is missing required configuration."""


class GrokResponseParseError(GrokServiceError):
    """Raised when the AI response cannot be parsed as valid JSON."""


class GrokAPIRequestError(GrokServiceError):
    """Raised when the AI provider returns an API or transport error."""


@dataclass(slots=True)
class GrokService:
    """Analyze influencer profiles using Google Gemini."""

    config: GrokConfig | None = None
    client: Any | None = None

    def __post_init__(self) -> None:
        """Load configuration and build a Gemini client if possible."""
        config = self.config or GrokConfig.from_env()
        self.config = config

        if not config.has_api_key:
            logger.warning("Missing Gemini API key; AI analysis will use defaults")
            self.client = None
            return

        if self.client is None:
            if config.api_key is None:
                logger.warning("Gemini API key is unavailable; AI analysis will use defaults")
                self.client = None
                return
            self.client = self._build_client(config.api_key)

    def analyze_influencer(self, influencer: Influencer) -> AIAnalysis:
        """Analyze one influencer profile and return structured AI insights."""
        prompt = self._build_prompt(influencer)
        logger.debug("Analyzing influencer '%s' with Gemini", influencer.handle)

        response_text = self._execute_request(prompt)
        if not response_text:
            return self._default_analysis(
                influencer,
                "AI analysis temporarily unavailable; using default scoring only",
            )

        try:
            analysis = AIAnalysis.from_json(response_text)
            logger.debug("Gemini analysis completed for '%s'", influencer.handle)
            return analysis
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse Gemini JSON response for '%s': %s", influencer.handle, exc)
            return self._default_analysis(
                influencer,
                "AI analysis temporarily unavailable; using default scoring only",
                details=f"Gemini returned invalid JSON: {exc}",
            )

    def _build_client(self, api_key: str) -> Any | None:
        """Create a Gemini client from the official SDK if installed."""
        try:
            genai_module = importlib.import_module("google.genai")
        except ModuleNotFoundError as exc:
            logger.error("Gemini SDK is not installed: %s", exc)
            return None

        client_factory = getattr(genai_module, "Client", None)
        if client_factory is None:
            logger.error("Gemini SDK Client class is unavailable")
            return None

        try:
            return client_factory(api_key=api_key)
        except Exception as exc:  # pragma: no cover - defensive SDK initialization guard
            logger.error("Failed to initialize Gemini client: %s", exc)
            return None

    def _execute_request(self, prompt: str) -> str | None:
        """Execute the model call with retries for transient failures."""
        config = self.config
        assert config is not None

        if self.client is None:
            logger.warning("Gemini client is unavailable; returning default analysis")
            return None

        retrying = Retrying(
            stop=stop_after_attempt(config.max_retries),
            wait=wait_exponential(
                multiplier=config.retry_initial_delay_seconds,
                min=config.retry_initial_delay_seconds,
                max=config.retry_max_delay_seconds,
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        last_error: Exception | None = None
        for attempt in retrying:
            with attempt:
                try:
                    return self._create_completion(prompt)
                except Exception as exc:  # pragma: no cover - SDK/network failures are environment-dependent
                    last_error = exc
                    logger.warning("Gemini request attempt failed: %s", exc)
                    raise

        if last_error is not None:
            logger.error("Gemini request failed after retries: %s", last_error)
        return None

    def _create_completion(self, prompt: str) -> str:
        """Make the actual API request and return the raw assistant content."""
        client = self.client
        config = self.config
        assert client is not None
        assert config is not None

        sdk_types = self._load_types_module()
        response_config = None
        if sdk_types is not None:
            response_config = sdk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=config.temperature,
                max_output_tokens=config.max_output_tokens,
            )

        response = client.models.generate_content(
            model=config.model,
            contents=prompt,
            config=response_config,
        )

        content = self._extract_text(response)
        if not content or not content.strip():
            raise GrokResponseParseError("Gemini returned an empty response")
        return content

    @staticmethod
    def _load_types_module() -> ModuleType | None:
        """Load Gemini SDK types if available."""
        try:
            return importlib.import_module("google.genai.types")
        except ModuleNotFoundError:
            return None

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text from a Gemini response object."""
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    return part_text
        return ""

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
    def _default_analysis(
        influencer: Influencer,
        summary: str,
        details: str | None = None,
    ) -> AIAnalysis:
        """Build a safe fallback AI analysis object."""
        return AIAnalysis(
            detected_language=influencer.language or "unknown",
            niche="unknown",
            government_support_score=0,
            political_orientation="unknown",
            confidence=0.0,
            summary=summary,
            keywords=[],
            reasoning=details or summary,
        )
