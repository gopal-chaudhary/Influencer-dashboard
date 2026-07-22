"""Final result object produced by the dashboard workflow."""

from __future__ import annotations

from dataclasses import dataclass

from models.ai_analysis import AIAnalysis
from models.influencer import Influencer
from models.score_result import ScoreResult


@dataclass(slots=True)
class EvaluatedInfluencer:
    """Bundle the influencer, AI analysis, and scoring output together."""

    influencer: Influencer
    ai_analysis: AIAnalysis
    score_result: ScoreResult
    rank: int = 0
    ai_analysis_performed: bool = False
