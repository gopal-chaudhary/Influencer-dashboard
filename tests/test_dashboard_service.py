from __future__ import annotations

from types import SimpleNamespace
from typing import cast
import unittest
from unittest.mock import MagicMock

from models import AIAnalysis, DashboardFilters, Influencer
from services.dashboard_service import DashboardWorkflowService
from services.grok_service import GrokService
from services.scoring_service import ScoringService


class DashboardWorkflowServiceTests(unittest.TestCase):
    def test_evaluate_influencers_ranks_results_and_calls_grok_once(self) -> None:
        influencers = [
            Influencer(
                name="High Score",
                handle="high",
                platform="Instagram",
                bio="Fashion creator and brand storyteller.",
                recent_content=["fashion", "creator"],
                followers=250_000,
                language="English",
            ),
            Influencer(
                name="Low Score",
                handle="low",
                platform="Instagram",
                bio="Lifestyle updates.",
                recent_content=["daily update"],
                followers=500,
                language="English",
            ),
        ]

        analyses = {
            "high": AIAnalysis(
                detected_language="English",
                niche="Fashion",
                government_support_score=90,
                political_orientation="supportive",
                confidence=0.8,
                summary="High confidence support.",
                keywords=["fashion"],
                reasoning="Positive policy mentions.",
            ),
            "low": AIAnalysis(
                detected_language="English",
                niche="Lifestyle",
                government_support_score=10,
                political_orientation="neutral",
                confidence=0.4,
                summary="Low support.",
                keywords=["lifestyle"],
                reasoning="Few relevant mentions.",
            ),
        }

        grok_service = SimpleNamespace(analyze_influencers=MagicMock(return_value=analyses))
        service = DashboardWorkflowService(
            grok_service=cast(GrokService, grok_service),
            scoring_service=ScoringService(),
        )

        ranked_results = service.evaluate_influencers(influencers)

        self.assertEqual(grok_service.analyze_influencers.call_count, 1)
        self.assertEqual(ranked_results[0].rank, 1)
        self.assertEqual(ranked_results[0].influencer.handle, "high")
        self.assertEqual(ranked_results[1].rank, 2)

    def test_filter_results_respects_search_and_filters(self) -> None:
        results = [
            self._build_evaluated_influencer("alice", "Instagram", "English", "Fashion", 50_000, 88.0),
            self._build_evaluated_influencer("bob", "TikTok", "Hindi", "Travel", 10_000, 45.0),
        ]
        filters = DashboardFilters(
            platform="Instagram",
            language="English",
            niche="Fashion",
            min_followers=20_000,
            min_score=80.0,
            search_query="ali",
        )

        filtered = DashboardWorkflowService.filter_results(results, filters)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].influencer.handle, "alice")
        self.assertEqual(filtered[0].rank, 1)

    @staticmethod
    def _build_evaluated_influencer(
        handle: str,
        platform: str,
        language: str,
        niche: str,
        followers: int,
        total_score: float,
    ):
        from models import EvaluatedInfluencer
        from models.score_result import ScoreResult

        influencer = Influencer(
            name=handle.title(),
            handle=handle,
            platform=platform,
            bio="Bio",
            recent_content=["content"],
            followers=followers,
            language=language,
        )
        ai_analysis = AIAnalysis(
            detected_language=language,
            niche=niche,
            government_support_score=50,
            political_orientation="neutral",
            confidence=0.5,
            summary="Summary",
            keywords=[niche.lower()],
            reasoning="Reasoning",
        )
        score_result = ScoreResult(
            total_score=total_score,
            score_breakdown={"language": 10.0},
            matched_languages=[language.lower()],
            matched_niches=[niche.lower()],
            remarks=["remark"],
        )
        return EvaluatedInfluencer(influencer=influencer, ai_analysis=ai_analysis, score_result=score_result)
