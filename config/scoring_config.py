"""Central scoring configuration for the influencer discovery engine.

This module holds the tunable weights and keyword sets in one place so the
scoring behavior can be adjusted without touching the service implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

LANGUAGE_WEIGHT = 20.0
NICHE_WEIGHT = 30.0
FOLLOWER_WEIGHT = 15.0
BIO_WEIGHT = 20.0
ENGAGEMENT_WEIGHT = 10.0
AI_WEIGHT = 15.0

TARGET_LANGUAGES: tuple[str, ...] = (
    "english",
    "hindi",
    "spanish",
)

TARGET_NICHES: tuple[str, ...] = (
    "fashion",
    "beauty",
    "fitness",
    "travel",
    "technology",
    "tech",
    "lifestyle",
    "business",
    "finance",
)

BIO_KEYWORDS: tuple[str, ...] = (
    "creator",
    "influencer",
    "brand",
    "community",
    "content",
    "storyteller",
    "guide",
)

FOLLOWER_CAP = 1_000_000.0
ENGAGEMENT_RATE_CAP = 0.20

# AI Analysis Configuration
# Number of top-ranked influencers to receive Gemini AI analysis.
# Remaining influencers show preliminary rule-based scores only.
# This reduces API usage while maintaining quality analysis for top candidates.
# Reduced to 2 for testing with new free tier account to minimize token usage
TOP_AI_ANALYSIS_COUNT = 2


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Store the weights and matching rules used by the scoring engine."""

    language_weight: float = LANGUAGE_WEIGHT
    niche_weight: float = NICHE_WEIGHT
    follower_weight: float = FOLLOWER_WEIGHT
    bio_weight: float = BIO_WEIGHT
    engagement_weight: float = ENGAGEMENT_WEIGHT
    ai_weight: float = AI_WEIGHT
    target_languages: tuple[str, ...] = TARGET_LANGUAGES
    target_niches: tuple[str, ...] = TARGET_NICHES
    bio_keywords: tuple[str, ...] = BIO_KEYWORDS
    follower_cap: float = FOLLOWER_CAP
    engagement_rate_cap: float = ENGAGEMENT_RATE_CAP
    top_ai_analysis_count: int = TOP_AI_ANALYSIS_COUNT

    def __post_init__(self) -> None:
        """Normalize and validate configuration values."""
        object.__setattr__(self, "target_languages", self._normalize_terms(self.target_languages))
        object.__setattr__(self, "target_niches", self._normalize_terms(self.target_niches))
        object.__setattr__(self, "bio_keywords", self._normalize_terms(self.bio_keywords))

        for field_name in (
            "language_weight",
            "niche_weight",
            "follower_weight",
            "bio_weight",
            "engagement_weight",
            "ai_weight",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")

        if self.follower_cap <= 0:
            raise ValueError("follower_cap must be greater than zero")

        if self.engagement_rate_cap <= 0:
            raise ValueError("engagement_rate_cap must be greater than zero")

        if self.top_ai_analysis_count < 0:
            raise ValueError("top_ai_analysis_count cannot be negative")

    @property
    def total_weight(self) -> float:
        """Return the sum of all configured weights."""
        return (
            self.language_weight
            + self.niche_weight
            + self.follower_weight
            + self.bio_weight
            + self.engagement_weight
            + self.ai_weight
        )

    @staticmethod
    def _normalize_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize keywords and target values for case-insensitive matching."""
        normalized_terms = tuple(term.strip().casefold() for term in terms if term.strip())
        if not normalized_terms:
            raise ValueError("Configuration lists cannot be empty")
        return normalized_terms
