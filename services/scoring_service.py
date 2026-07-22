"""Reusable scoring engine for influencer evaluation.

The service is intentionally independent of Streamlit so it can be reused by the
UI, tests, automation, or future API endpoints without modification.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from config.scoring_config import ScoringConfig
from models import Influencer
from models.score_result import ScoreResult


@runtime_checkable
class AIScoringStrategy(Protocol):
    """Strategy interface for AI-assisted orientation scoring."""

    def score(self, influencer: Influencer, config: ScoringConfig) -> tuple[float, list[str]]:
        """Return a normalized score and remarks for the AI criterion."""
        ...


@dataclass(slots=True)
class PlaceholderAIScoringStrategy:
    """Default AI strategy used until Grok is integrated.

    The strategy deliberately returns a neutral score and a placeholder remark so
    the rest of the scoring engine can remain stable while the AI layer is still
    under development.
    """

    def score(self, influencer: Influencer, config: ScoringConfig) -> tuple[float, list[str]]:
        return 0.0, ["AI orientation scoring is pending Grok integration."]


class ScoringService:
    """Score influencers using configurable weighted business rules."""

    def __init__(
        self,
        config: ScoringConfig | None = None,
        ai_scorer: AIScoringStrategy | None = None,
    ) -> None:
        self._config = config or ScoringConfig()
        self._ai_scorer = ai_scorer or PlaceholderAIScoringStrategy()

    def score(self, influencer: Influencer) -> ScoreResult:
        """Return the weighted score result for one influencer."""
        language_score, matched_languages, language_remarks = self._score_language(influencer)
        niche_score, matched_niches, niche_remarks = self._score_niche(influencer)
        bio_score, bio_remarks = self._score_bio(influencer)
        follower_score, follower_remarks = self._score_followers(influencer)
        engagement_score, engagement_remarks = self._score_engagement(influencer)
        ai_score, ai_remarks = self._score_ai_orientation(influencer)

        total_weight = self._config.total_weight
        score_breakdown = {
            "language": self._weighted_contribution(language_score, self._config.language_weight, total_weight),
            "niche": self._weighted_contribution(niche_score, self._config.niche_weight, total_weight),
            "bio": self._weighted_contribution(bio_score, self._config.bio_weight, total_weight),
            "followers": self._weighted_contribution(follower_score, self._config.follower_weight, total_weight),
            "engagement": self._weighted_contribution(engagement_score, self._config.engagement_weight, total_weight),
            "ai_orientation": self._weighted_contribution(ai_score, self._config.ai_weight, total_weight),
        }

        total_score = round(sum(score_breakdown.values()), 2)
        remarks = [
            *language_remarks,
            *niche_remarks,
            *bio_remarks,
            *follower_remarks,
            *engagement_remarks,
            *ai_remarks,
        ]

        return ScoreResult(
            total_score=total_score,
            score_breakdown=score_breakdown,
            matched_languages=matched_languages,
            matched_niches=matched_niches,
            remarks=remarks,
        )

    def _score_language(self, influencer: Influencer) -> tuple[float, list[str], list[str]]:
        """Score whether the influencer language matches a target language."""
        normalized_language = influencer.language.strip().casefold()
        if not normalized_language:
            return 0.0, [], ["Language not provided; language score set to 0."]

        for target_language in self._config.target_languages:
            if normalized_language == target_language:
                return (
                    1.0,
                    [self._display_term(target_language)],
                    [f"Language match found: {self._display_term(target_language)}."],
                )

        return 0.0, [], [f"No configured language match for '{influencer.language}'."]

    def _score_niche(self, influencer: Influencer) -> tuple[float, list[str], list[str]]:
        """Score how many configured niche keywords appear in the influencer text."""
        searchable_text = self._build_search_text(influencer)
        if not searchable_text:
            return 0.0, [], ["No bio or recent content available for niche matching."]

        matched_niches = [
            niche for niche in self._config.target_niches if self._contains_term(searchable_text, niche)
        ]
        if not matched_niches:
            return 0.0, [], ["No niche keywords matched the configured target niches."]

        score = len(matched_niches) / len(self._config.target_niches)
        return (
            min(score, 1.0),
            [self._display_term(niche) for niche in matched_niches],
            [f"Niche matches found: {', '.join(self._display_term(niche) for niche in matched_niches)}."],
        )

    def _score_bio(self, influencer: Influencer) -> tuple[float, list[str]]:
        """Score bio relevance against configured bio keywords."""
        bio_text = influencer.bio.strip().casefold()
        if not bio_text:
            return 0.0, ["Bio not provided; bio score set to 0."]

        matched_keywords = [
            keyword for keyword in self._config.bio_keywords if self._contains_term(bio_text, keyword)
        ]
        if not matched_keywords:
            return 0.0, ["Bio did not match any configured relevance keywords."]

        score = len(matched_keywords) / len(self._config.bio_keywords)
        return min(score, 1.0), [
            f"Bio relevance matches: {', '.join(self._display_term(keyword) for keyword in matched_keywords)}."
        ]

    def _score_followers(self, influencer: Influencer) -> tuple[float, list[str]]:
        """Score follower count using a capped logarithmic scale."""
        followers = influencer.followers
        if followers <= 0:
            return 0.0, ["Follower count is zero; follower score set to 0."]

        normalized = math.log10(followers + 1) / math.log10(self._config.follower_cap + 1)
        score = min(max(normalized, 0.0), 1.0)
        return score, [f"Follower score calculated from {followers:,} followers."]

    def _score_engagement(self, influencer: Influencer) -> tuple[float, list[str]]:
        """Score engagement if an engagement field is available on the model.

        The current domain model does not define a dedicated engagement attribute,
        so this method looks for common attribute names and falls back to a neutral
        placeholder when no metric is available.
        """
        engagement_value = self._extract_numeric_attribute(
            influencer,
            ("engagement_score", "engagement_rate", "avg_engagement_rate"),
        )
        if engagement_value is None:
            return 0.0, ["Engagement data not available; engagement score set to 0."]

        normalized_rate = engagement_value
        if normalized_rate > 1:
            normalized_rate = normalized_rate / 100.0

        score = min(max(normalized_rate / self._config.engagement_rate_cap, 0.0), 1.0)
        return score, ["Engagement score calculated from available engagement data."]

    def _score_ai_orientation(self, influencer: Influencer) -> tuple[float, list[str]]:
        """Score political/supportive orientation via the AI strategy."""
        ai_score, remarks = self._ai_scorer.score(influencer, self._config)
        return min(max(ai_score, 0.0), 1.0), remarks

    def _weighted_contribution(self, score: float, weight: float, total_weight: float) -> float:
        """Convert a normalized score into a weighted 0-100 contribution."""
        if total_weight <= 0:
            return 0.0
        return round((score * weight / total_weight) * 100, 2)

    def _build_search_text(self, influencer: Influencer) -> str:
        """Combine searchable influencer text into one normalized string."""
        content_text = " ".join(influencer.recent_content)
        combined_text = " ".join((influencer.bio, content_text)).strip().casefold()
        return combined_text

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        """Return ``True`` when the term appears as a readable phrase in text."""
        pattern = rf"\b{re.escape(term)}\b"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    @staticmethod
    def _display_term(term: str) -> str:
        """Convert normalized terms into a display-friendly label."""
        return term.replace("_", " ")

    @staticmethod
    def _extract_numeric_attribute(influencer: Influencer, attribute_names: tuple[str, ...]) -> float | None:
        """Return the first usable numeric attribute from a list of candidates."""
        for attribute_name in attribute_names:
            value = getattr(influencer, attribute_name, None)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                if math.isnan(value) if isinstance(value, float) else False:
                    continue
                if value < 0:
                    continue
                return float(value)
        return None
