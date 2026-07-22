"""Workflow service that connects Gemini analysis and scoring.

This service owns the business logic for transforming raw influencers into
ranked, evaluation-ready results. It deliberately stays independent of Streamlit
so the same logic can be reused by tests or future API endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from utils import get_logger

from config.scoring_config import ScoringConfig
from models import AIAnalysis, DashboardFilters, EvaluatedInfluencer, Influencer
from services.gemini_service import GeminiAPIRequestError, GeminiConfigurationError, GeminiResponseParseError, GeminiService
from services.scoring_service import ScoringService


logger = get_logger(__name__)


@dataclass(slots=True)
class DashboardWorkflowService:
    """Coordinate Gemini analysis, scoring, ranking, and filtering."""

    gemini_service: GeminiService
    scoring_service: ScoringService

    @classmethod
    def create_default(cls) -> "DashboardWorkflowService":
        """Create a workflow service using the project's default configuration."""
        gemini_service = GeminiService()
        scoring_service = ScoringService(ScoringConfig())
        return cls(gemini_service=gemini_service, scoring_service=scoring_service)

    def evaluate_influencers(self, influencers: Sequence[Influencer]) -> list[EvaluatedInfluencer]:
        """Analyze and score influencers using a two-tier approach.
        
        Workflow:
        1. Compute preliminary rule-based scores for ALL influencers.
        2. Sort by preliminary score and select the Top N for AI analysis.
        3. Call Gemini only on the Top N influencers.
        4. Re-score the Top N with their AI analysis results.
        5. Leave the remaining influencers with preliminary scores only.
        6. Return all results ranked by final total score.
        
        This reduces API usage while ensuring high-quality analysis for top candidates.
        """
        if not influencers:
            return []

        logger.info("Evaluating %d influencers (two-tier approach)", len(influencers))

        # Step 1: Score all influencers with preliminary (rule-based only) scores
        logger.info("Step 1: Computing preliminary rule-based scores for all %d influencers", len(influencers))
        preliminary_evaluations = [
            self._evaluate_preliminary(influencer) for influencer in influencers
        ]

        # Step 2: Sort by preliminary score and select Top N
        config = self.scoring_service._config
        top_n = max(1, config.top_ai_analysis_count)
        sorted_by_preliminary = sorted(
            preliminary_evaluations,
            key=lambda item: (
                -item.score_result.preliminary_score,
                -item.influencer.followers,
                item.influencer.name.casefold(),
            ),
        )
        
        top_influencers = sorted_by_preliminary[:top_n]
        remaining_influencers = sorted_by_preliminary[top_n:]

        logger.info("Step 2: Selected Top %d influencers for AI analysis (out of %d)", len(top_influencers), len(influencers))

        # Step 3 & 4: Analyze Top N with Gemini and re-score
        logger.info("Step 3-4: Analyzing Top %d influencers with Gemini", len(top_influencers))
        top_influencer_objects = [eval_result.influencer for eval_result in top_influencers]
        ai_analysis_map = self._analyze_influencers(top_influencer_objects)

        top_with_ai = [
            self._evaluate_with_ai(
                eval_result.influencer,
                ai_analysis_map.get(self._normalize_handle(eval_result.influencer.handle)),
                ai_analysis_performed=True,
            )
            for eval_result in top_influencers
        ]

        # Step 5: Keep remaining with preliminary scores (no AI analysis)
        logger.info("Step 5: Keeping remaining %d influencers with preliminary scores only", len(remaining_influencers))
        remaining_with_no_ai = [
            self._evaluate_with_ai(
                eval_result.influencer,
                self._not_analyzed_fallback(eval_result.influencer),
                ai_analysis_performed=False,
            )
            for eval_result in remaining_influencers
        ]

        # Step 6: Merge and rank all results
        all_evaluated = top_with_ai + remaining_with_no_ai
        ranked_influencers = self._rank_evaluations(all_evaluated)

        logger.info(
            "Finished evaluating %d influencers (Top %d analyzed with AI, %d with preliminary scores only)",
            len(ranked_influencers),
            len(top_with_ai),
            len(remaining_with_no_ai),
        )
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

    def _analyze_influencers(self, influencers: Sequence[Influencer]) -> dict[str, AIAnalysis]:
        """Analyze influencers using a single Gemini batch request when possible."""
        try:
            return self.gemini_service.analyze_influencers(influencers)
        except (GeminiConfigurationError, GeminiAPIRequestError, GeminiResponseParseError) as exc:
            logger.warning("Falling back to default AI analyses for %d influencers: %s", len(influencers), exc)
            return {
                self._normalize_handle(influencer.handle): AIAnalysis(
                    detected_language=influencer.language or "unknown",
                    niche="unknown",
                    government_support_score=0,
                    political_orientation="unknown",
                    confidence=0.0,
                    summary="AI analysis temporarily unavailable; using default scoring only",
                    keywords=[],
                    reasoning=f"AI analysis temporarily unavailable; using default scoring only. Details: {exc}",
                )
                for influencer in influencers
            }

    def _evaluate_preliminary(self, influencer: Influencer) -> EvaluatedInfluencer:
        """Evaluate influencer with preliminary (rule-based only) scoring.
        
        This is used in the first pass to quickly rank all influencers before
        expensive Gemini calls.
        """
        score_result = self.scoring_service.score_preliminary(influencer)
        fallback_analysis = AIAnalysis(
            detected_language=influencer.language or "unknown",
            niche="unknown",
            government_support_score=0,
            political_orientation="unknown",
            confidence=0.0,
            summary="",
            keywords=[],
            reasoning="",
        )
        return EvaluatedInfluencer(
            influencer=influencer,
            ai_analysis=fallback_analysis,
            score_result=score_result,
            rank=0,
            ai_analysis_performed=False,
        )

    def _evaluate_with_ai(
        self,
        influencer: Influencer,
        ai_analysis: AIAnalysis | None,
        ai_analysis_performed: bool,
    ) -> EvaluatedInfluencer:
        """Evaluate influencer with full scoring (including AI if provided).
        
        Args:
            influencer: The influencer to evaluate.
            ai_analysis: The AI analysis result, or None/fallback if not performed.
            ai_analysis_performed: True if this influencer was actually analyzed by Gemini.
        """
        score_result = self.scoring_service.score(influencer, ai_analysis)
        return EvaluatedInfluencer(
            influencer=influencer,
            ai_analysis=ai_analysis or self._not_analyzed_fallback(influencer),
            score_result=score_result,
            rank=0,
            ai_analysis_performed=ai_analysis_performed,
        )

    def _evaluate_influencer(self, influencer: Influencer, ai_analysis: AIAnalysis | None) -> EvaluatedInfluencer:
        """Legacy method: evaluate one influencer with AI analysis (deprecated)."""
        score_result = self.scoring_service.score(influencer, ai_analysis)
        return EvaluatedInfluencer(
            influencer=influencer,
            ai_analysis=ai_analysis or self._fallback_analysis(influencer),
            score_result=score_result,
            ai_analysis_performed=True,
        )

    @staticmethod
    def _not_analyzed_fallback(influencer: Influencer) -> AIAnalysis:
        """Create fallback analysis for influencers not selected for AI analysis.
        
        This clearly indicates that the influencer was ranked below the threshold
        and was not sent to Gemini.
        """
        return AIAnalysis(
            detected_language=influencer.language or "unknown",
            niche="unknown",
            government_support_score=0,
            political_orientation="unknown",
            confidence=0.0,
            summary="Not analyzed (outside Top 10 by preliminary score)",
            keywords=[],
            reasoning="This influencer ranked outside the top threshold and was not analyzed by AI to reduce API costs.",
        )

    @staticmethod
    def _fallback_analysis(influencer: Influencer) -> AIAnalysis:
        """Construct a safe fallback analysis for a single influencer (legacy)."""
        return AIAnalysis(
            detected_language=influencer.language or "unknown",
            niche="unknown",
            government_support_score=0,
            political_orientation="unknown",
            confidence=0.0,
            summary="AI analysis temporarily unavailable; using default scoring only",
            keywords=[],
            reasoning="AI analysis temporarily unavailable; using default scoring only",
        )

    @staticmethod
    def _normalize_handle(handle: str) -> str:
        """Normalize handles so returned analyses can be matched reliably."""
        return handle.strip().lstrip("@").casefold()

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
