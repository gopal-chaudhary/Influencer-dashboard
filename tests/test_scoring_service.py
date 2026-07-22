from __future__ import annotations

import unittest

from config.scoring_config import ScoringConfig
from models import AIAnalysis, Influencer
from services.scoring_service import ScoringService


class ScoringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ScoringService(ScoringConfig())

    def test_score_uses_ai_analysis_and_business_rules(self) -> None:
        influencer = Influencer(
            name="Alice Creator",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator and storyteller for travel brands.",
            recent_content=["fashion haul", "travel vlog"],
            followers=120_000,
            language="English",
        )
        ai_analysis = AIAnalysis(
            detected_language="English",
            niche="Fashion",
            government_support_score=80,
            political_orientation="supportive",
            confidence=0.75,
            summary="Strong support for public campaigns.",
            keywords=["fashion", "creator"],
            reasoning="Mentions community initiatives and public programs.",
        )

        result = self.service.score(influencer, ai_analysis)

        self.assertGreater(result.total_score, 0.0)
        self.assertEqual(result.matched_languages, ["english"])
        self.assertIn("fashion", result.matched_niches)
        self.assertIn("travel", result.matched_niches)
        self.assertIn("ai_orientation", result.score_breakdown)
        self.assertGreater(result.score_breakdown["ai_orientation"], 0.0)
        self.assertTrue(any("AI analysis" in remark for remark in result.remarks))
