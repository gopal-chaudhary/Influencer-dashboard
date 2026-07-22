"""Structured AI analysis model returned by the Gemini service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class AIAnalysis:
    """Represent the structured output of an AI profile analysis."""

    detected_language: str
    niche: str
    government_support_score: int
    political_orientation: str
    confidence: float
    summary: str
    keywords: list[str] = field(default_factory=list)
    reasoning: str = ""

    def __post_init__(self) -> None:
        """Normalize and validate the analysis payload."""
        self.detected_language = self._clean_text(self.detected_language, "unknown")
        self.niche = self._clean_text(self.niche, "unknown")
        self.political_orientation = self._clean_text(self.political_orientation, "unknown")
        self.summary = self._clean_text(self.summary, "")
        self.reasoning = self._clean_text(self.reasoning, "")
        self.keywords = self._normalize_keywords(self.keywords)
        self.government_support_score = self._normalize_score(self.government_support_score)
        self.confidence = self._normalize_confidence(self.confidence)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AIAnalysis":
        """Create an analysis model from a dictionary-like payload."""
        return cls(
            detected_language=data.get("detected_language", "unknown"),
            niche=data.get("niche", "unknown"),
            government_support_score=data.get("government_support_score", 0),
            political_orientation=data.get("political_orientation", "unknown"),
            confidence=data.get("confidence", 0.0),
            summary=data.get("summary", ""),
            keywords=data.get("keywords", []),
            reasoning=data.get("reasoning", ""),
        )

    @classmethod
    def from_json(cls, json_text: str) -> "AIAnalysis":
        """Parse a JSON string into an ``AIAnalysis`` instance."""
        cleaned_text = cls._strip_code_fences(json_text)
        payload = json.loads(cleaned_text)
        if not isinstance(payload, dict):
            raise ValueError("AI analysis JSON must contain an object")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the analysis."""
        return {
            "detected_language": self.detected_language,
            "niche": self.niche,
            "government_support_score": self.government_support_score,
            "political_orientation": self.political_orientation,
            "confidence": self.confidence,
            "summary": self.summary,
            "keywords": list(self.keywords),
            "reasoning": self.reasoning,
        }

    @staticmethod
    def _clean_text(value: Any, fallback: str) -> str:
        """Normalize a text value while keeping a sensible fallback."""
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    @staticmethod
    def _normalize_keywords(value: Any) -> list[str]:
        """Normalize keyword output into a trimmed list of strings."""
        if value is None:
            return []

        if isinstance(value, str):
            items = re.split(r"\s*(?:,|;|\|)\s*", value.strip())
            return [item for item in (part.strip() for part in items) if item]

        if not isinstance(value, (list, tuple)):
            return [str(value).strip()] if str(value).strip() else []

        normalized_items: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                normalized_items.append(text)
        return normalized_items

    @staticmethod
    def _normalize_score(value: Any) -> int:
        """Normalize the government support score into a 0-100 integer."""
        if value is None:
            return 0

        if isinstance(value, bool):
            raise TypeError("government_support_score must be numeric")

        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("government_support_score must be numeric") from exc

        if score < 0:
            score = 0
        if score <= 1:
            score *= 100
        if score > 100:
            score = 100
        return int(round(score))

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        """Normalize confidence into a 0.0-1.0 floating-point score."""
        if value is None:
            return 0.0

        if isinstance(value, bool):
            raise TypeError("confidence must be numeric")

        try:
            confidence = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("confidence must be numeric") from exc

        if confidence < 0:
            confidence = 0.0
        if confidence > 1:
            confidence = confidence / 100.0 if confidence <= 100 else 1.0
        return round(min(confidence, 1.0), 4)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove common markdown code fences from model output."""
        cleaned_text = text.strip()
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
        return cleaned_text.strip()
