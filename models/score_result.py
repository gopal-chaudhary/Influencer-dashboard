"""Scoring result model for influencer evaluation.

This module stays independent of Streamlit and persistence layers so the scoring
engine can be reused from the UI, tests, background jobs, or future APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ScoreResult:
    """Hold the outcome of scoring one influencer.

    Attributes:
        total_score: Final normalized score on a 0-100 scale.
        preliminary_score: Rule-based score before AI analysis (used for ranking).
        score_breakdown: Contribution of each scoring criterion to the final
            score.
        matched_languages: Languages that matched the configured targets.
        matched_niches: Niches that matched the configured targets.
        remarks: Human-readable notes about the scoring decision.
    """

    total_score: float
    preliminary_score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    matched_languages: list[str] = field(default_factory=list)
    matched_niches: list[str] = field(default_factory=list)
    remarks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the score result."""
        return {
            "total_score": self.total_score,
            "score_breakdown": dict(self.score_breakdown),
            "matched_languages": list(self.matched_languages),
            "matched_niches": list(self.matched_niches),
            "remarks": list(self.remarks),
        }
