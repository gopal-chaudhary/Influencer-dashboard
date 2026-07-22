from __future__ import annotations

import unittest

from models import AIAnalysis


class AIAnalysisTests(unittest.TestCase):
    def test_from_json_strips_code_fences_and_normalizes_values(self) -> None:
        payload = """```json
        {
            "detected_language": "English",
            "niche": "Fashion",
            "government_support_score": 85,
            "political_orientation": "supportive",
            "confidence": 72,
            "summary": "Supports campaigns",
            "keywords": ["fashion", "creator"],
            "reasoning": "Clear support for initiatives"
        }
        ```"""

        analysis = AIAnalysis.from_json(payload)

        self.assertEqual(analysis.detected_language, "English")
        self.assertEqual(analysis.niche, "Fashion")
        self.assertEqual(analysis.government_support_score, 85)
        self.assertEqual(analysis.political_orientation, "supportive")
        self.assertAlmostEqual(analysis.confidence, 0.72)
        self.assertEqual(analysis.summary, "Supports campaigns")
        self.assertEqual(analysis.keywords, ["fashion", "creator"])
        self.assertEqual(analysis.reasoning, "Clear support for initiatives")
