"""Configuration package for the Influencer Discovery Dashboard."""

from .gemini_config import GeminiConfig
from .scoring_config import (
    AI_WEIGHT,
    BIO_KEYWORDS,
    BIO_WEIGHT,
    ENGAGEMENT_RATE_CAP,
    ENGAGEMENT_WEIGHT,
    FOLLOWER_CAP,
    FOLLOWER_WEIGHT,
    LANGUAGE_WEIGHT,
    NICHE_WEIGHT,
    TARGET_LANGUAGES,
    TARGET_NICHES,
    ScoringConfig,
)

__all__ = [
    "AI_WEIGHT",
    "BIO_KEYWORDS",
    "BIO_WEIGHT",
    "ENGAGEMENT_RATE_CAP",
    "ENGAGEMENT_WEIGHT",
    "FOLLOWER_CAP",
    "FOLLOWER_WEIGHT",
    "GeminiConfig",
    "LANGUAGE_WEIGHT",
    "NICHE_WEIGHT",
    "TARGET_LANGUAGES",
    "TARGET_NICHES",
    "ScoringConfig",
]
