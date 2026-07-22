"""Workflow service that connects Grok analysis and scoring.

This service owns the business logic for transforming raw influencers into
ranked, evaluation-ready results. It deliberately stays independent of Streamlit
so the same logic can be reused by tests or future API endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from config.scoring_config import ScoringConfig
from models import AIAnalysis, DashboardFilters, EvaluatedInfluencer, Influencer
from services.grok_service import GrokAPIRequestError, GrokConfigurationError, GrokResponseParseError, GrokService
from services.scoring_service import ScoringService


@dataclass(slots=True)
class DashboardWorkflowService:
    """Coordinate Grok analysis, scoring, ranking, and filtering."""

    grok_service: GrokService
    scoring_service: ScoringService

    @classmethod
    def create_default(cls) -> "DashboardWorkflowService":
        """Create a workflow service using the project's default configuration."""
        grok_service = GrokService()
        scoring_service = ScoringService(ScoringConfig())
        return cls(grok_service=grok_service, scoring_service=scoring_service)

    def evaluate_influencers(self, influencers: Sequence[Influencer]) -> list[EvaluatedInfluencer]:
        """Analyze and score each influencer, then return ranked results."""
        evaluated_influencers = [self._evaluate_influencer(influencer) for influencer in influencers]
        ranked_influencers = self._rank_evaluations(evaluated_influencers)
        return ranked_influencers

    @staticmethod
    def filter_results(
        evaluated_influencers: Sequence[EvaluatedInfluencer],
        filters: DashboardFilters,
    ) -> list[EvaluatedInfluencer]:
        """Apply search and filter criteria to the ranked influencer list."""
        filtered_results: list[EvaluatedInfluencer] = []
        search_query = filters.search_query.strip().casefold()

        for result in evaluated_influencers:
            if filters.platform and result.influencer.platform.casefold() != filters.platform.casefold():
                continue
            if filters.language and result.ai_analysis.detected_language.casefold() != filters.language.casefold():
                continue
            if filters.niche and result.ai_analysis.niche.casefold() != filters.niche.casefold():
                continue
            if result.influencer.followers < filters.min_followers:
                continue
            if result.score_result.total_score < filters.min_score:
                continue
            if search_query and search_query not in result.influencer.name.casefold() and search_query not in result.influencer.handle.casefold():
                continue
            filtered_results.append(result)

        return DashboardWorkflowService._rank_evaluations(filtered_results)

    def _evaluate_influencer(self, influencer: Influencer) -> EvaluatedInfluencer:
        """Evaluate one influencer and return the bundled result object."""
        ai_analysis = self._analyze_with_fallback(influencer)
        score_result = self.scoring_service.score(influencer, ai_analysis)
        return EvaluatedInfluencer(influencer=influencer, ai_analysis=ai_analysis, score_result=score_result)

    def _analyze_with_fallback(self, influencer: Influencer) -> AIAnalysis:
        """Analyze an influencer and fall back to a neutral result on failure."""
        try:
            return self.grok_service.analyze_influencer(influencer)
        except (GrokConfigurationError, GrokAPIRequestError, GrokResponseParseError) as exc:
            return AIAnalysis(
                detected_language=influencer.language or "unknown",
                niche="unknown",
                government_support_score=0,
                political_orientation="unknown",
                confidence=0.0,
                summary=f"AI analysis unavailable: {exc}",
                keywords=[],
                reasoning=str(exc),
            )

    @staticmethod
    def _rank_evaluations(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> list[EvaluatedInfluencer]:
        """Sort by total score and assign rank values."""
        ranked_results = sorted(
            evaluated_influencers,
            key=lambda item: (
                -item.score_result.total_score,
                -item.influencer.followers,
                item.influencer.name.casefold(),
                item.influencer.handle.casefold(),
            ),
        )
        for index, result in enumerate(ranked_results, start=1):
            result.rank = index
        return list(ranked_results)
