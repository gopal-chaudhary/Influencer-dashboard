"""Reusable service for analyzing influencers with Google Gemini.

The service keeps the same public interface as the previous AI integration so
research, ranking, and the UI can keep using the same architecture.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Sequence

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.gemini_config import GeminiConfig
from models import AIAnalysis, Influencer
from utils import get_logger


logger = get_logger(__name__)


class GeminiServiceError(Exception):
    """Base class for AI service errors."""


class GeminiConfigurationError(GeminiServiceError):
    """Raised when the AI service is missing required configuration."""


class GeminiResponseParseError(GeminiServiceError):
    """Raised when the AI response cannot be parsed as valid JSON."""


class GeminiAPIRequestError(GeminiServiceError):
    """Raised when the AI provider returns an API or transport error."""


@dataclass(slots=True)
class GeminiService:
    """Analyze influencer profiles using Google Gemini."""

    config: GeminiConfig | None = None
    client: Any | None = None

    def __post_init__(self) -> None:
        """Load configuration and build a Gemini client if possible."""
        config = self.config or GeminiConfig.from_env()
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
        analysis_map = self.analyze_influencers([influencer])
        normalized_handle = self._normalize_handle(influencer.handle)
        analysis = analysis_map.get(normalized_handle)
        if analysis is not None:
            return analysis

        return self._default_analysis(
            influencer,
            "AI analysis temporarily unavailable; using default scoring only",
        )

    def analyze_influencers(self, influencers: Sequence[Influencer]) -> dict[str, AIAnalysis]:
        """Analyze many influencers in one Gemini request.

        The returned mapping is keyed by normalized handle so the workflow layer can
        consume a single batch response without changing the UI or scoring layer.
        """
        if not influencers:
            return {}

        prompt = self._build_batch_prompt(influencers)
        logger.debug("Analyzing %d influencers with Gemini in a single request", len(influencers))

        try:
            response_text = self._execute_request_with_model_fallback(prompt)
            if not response_text:
                return self._default_analysis_map(influencers)

            return self._parse_batch_response(response_text, influencers)
        except GeminiResponseParseError as exc:
            logger.warning("Gemini batch response could not be parsed: %s", exc)
            return self._default_analysis_map(influencers, details=str(exc))
        except Exception as exc:  # pragma: no cover - environment-specific SDK failures
            logger.error("Gemini batch request failed: %s", exc, exc_info=True)
            return self._default_analysis_map(influencers, details=str(exc))

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

    def _execute_request_with_model_fallback(self, prompt: str) -> str | None:
        """Try configured Gemini models until one returns a usable response."""
        config = self.config
        assert config is not None

        last_error: Exception | None = None
        for model_name in config.model_candidates:
            try:
                return self._execute_request(prompt, model_name)
            except Exception as exc:  # pragma: no cover - provider errors are environment-dependent
                last_error = exc
                if self._is_model_unavailable_error(exc):
                    logger.warning("Gemini model '%s' unavailable; trying fallback model", model_name)
                    continue
                raise

        if last_error is not None:
            logger.error("All configured Gemini models failed: %s", last_error)
        return None

    def _execute_request(self, prompt: str, model_name: str) -> str | None:
        """Execute one model call with retries for transient failures."""
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
                    return self._create_completion(prompt, model_name)
                except Exception as exc:  # pragma: no cover - SDK/network failures are environment-dependent
                    last_error = exc
                    logger.warning("Gemini request attempt failed for model '%s': %s", model_name, exc)
                    raise

        if last_error is not None:
            logger.error("Gemini request failed after retries: %s", last_error)
        return None

    def _create_completion(self, prompt: str, model_name: str) -> str:
        """Make the actual API request and return the raw assistant content."""
        client = self.client
        config = self.config
        assert client is not None
        assert config is not None

        if hasattr(client, "interactions") and callable(getattr(client.interactions, "create", None)):
            response = client.interactions.create(
                model=model_name,
                input=prompt,
                timeout=config.timeout_seconds,
            )
        else:
            raise GeminiServiceError(
                "Gemini SDK client does not support interactions.create; ensure google-genai is installed and up to date"
            )

        content = self._extract_text(response)
        if not content or not content.strip():
            raise GeminiResponseParseError("Gemini returned an empty response")
        return content

    @staticmethod
    def _is_model_unavailable_error(error: Exception) -> bool:
        """Return true when Gemini says a model is unavailable or not found."""
        error_text = str(error).casefold()
        return "not_found" in error_text or "model" in error_text and "not" in error_text and "available" in error_text

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text from a Gemini response object."""
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
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
        return self._build_batch_prompt([influencer])

    def _build_batch_prompt(self, influencers: Sequence[Influencer]) -> str:
        """Build a prompt for batch JSON analysis.

        The model is instructed to return a JSON object containing a ``results``
        array with one object per influencer, each including the influencer handle
        so we can map the response back to the original dataset.
        """
        influencer_blocks: list[str] = []
        for influencer in influencers:
            recent_content = "\n".join(f"- {item}" for item in influencer.recent_content) or "- none"
            influencer_blocks.append(
                "\n".join(
                    (
                        f"Handle: {influencer.handle}",
                        f"Name: {influencer.name}",
                        f"Platform: {influencer.platform}",
                        f"Language: {influencer.language or 'unknown'}",
                        f"Bio: {influencer.bio or 'none'}",
                        f"Recent content:\n{recent_content}",
                        f"Followers: {influencer.followers}",
                    )
                )
            )

        return (
            "Analyze the following influencer profiles and return a single JSON object only.\n\n"
            "Return exactly this structure:\n"
            "{\n"
            '  "results": [\n'
            "    {\n"
            '      "handle": "",\n'
            '      "detected_language": "",\n'
            '      "niche": "",\n'
            '      "government_support_score": 0,\n'
            '      "political_orientation": "",\n'
            '      "confidence": 0,\n'
            '      "summary": "",\n'
            '      "keywords": [],\n'
            '      "reasoning": ""\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Return JSON only. No markdown, no prose, no code fences.\n"
            "- Include one result for each influencer.\n"
            "- Preserve each influencer handle exactly so the results can be matched.\n"
            "- Use the bio, recent content, language, and followers fields.\n"
            "- Identify the main niche.\n"
            "- Assess whether the content appears supportive of government initiatives.\n"
            "- Provide a confidence score from 0 to 1.\n\n"
            + "\n\n".join(influencer_blocks)
        )

    def _parse_batch_response(self, response_text: str, influencers: Sequence[Influencer]) -> dict[str, AIAnalysis]:
        """Parse a batch Gemini response into a handle-indexed mapping."""
        cleaned_text = self._strip_code_fences(response_text)
        payload = json.loads(cleaned_text)

        if isinstance(payload, list):
            results_payload = payload
        elif isinstance(payload, dict):
            results_payload = payload.get("results", [])
        else:
            raise GeminiResponseParseError("Gemini batch response must be a JSON object or array")

        if not isinstance(results_payload, list):
            raise GeminiResponseParseError("Gemini batch response missing a results array")

        normalized_handles = {self._normalize_handle(influencer.handle): influencer for influencer in influencers}
        analyses: dict[str, AIAnalysis] = {}
        for item in results_payload:
            if not isinstance(item, dict):
                continue

            handle_value = item.get("handle")
            if not isinstance(handle_value, str) or not handle_value.strip():
                continue

            normalized_handle = self._normalize_handle(handle_value)
            source_influencer = normalized_handles.get(normalized_handle)
            if source_influencer is None:
                continue

            analysis = AIAnalysis.from_dict(
                {
                    "detected_language": item.get("detected_language", source_influencer.language or "unknown"),
                    "niche": item.get("niche", "unknown"),
                    "government_support_score": item.get("government_support_score", 0),
                    "political_orientation": item.get("political_orientation", "unknown"),
                    "confidence": item.get("confidence", 0.0),
                    "summary": item.get("summary", ""),
                    "keywords": item.get("keywords", []),
                    "reasoning": item.get("reasoning", ""),
                }
            )
            analyses[normalized_handle] = analysis

        if not analyses:
            raise GeminiResponseParseError("Gemini batch response did not contain usable results")

        return analyses

    def _default_analysis_map(
        self,
        influencers: Sequence[Influencer],
        details: str | None = None,
    ) -> dict[str, AIAnalysis]:
        """Create default analyses for a set of influencers."""
        return {
            self._normalize_handle(influencer.handle): self._default_analysis(
                influencer,
                "AI analysis temporarily unavailable; using default scoring only",
                details=details,
            )
            for influencer in influencers
        }

    @staticmethod
    def _normalize_handle(handle: str) -> str:
        """Normalize handles so returned results can be matched reliably."""
        return handle.strip().lstrip("@").casefold()

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences if Gemini wraps the JSON response."""
        cleaned_text = text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.split("\n", 1)[1] if "\n" in cleaned_text else cleaned_text
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        if cleaned_text.lower().startswith("json\n"):
            cleaned_text = cleaned_text[5:]
        return cleaned_text.strip()

    def _default_analysis(
        self,
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
