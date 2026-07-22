from __future__ import annotations

from io import BytesIO
import unittest

import pandas as pd

from models import AIAnalysis, DashboardFilters, EvaluatedInfluencer, Influencer
from models.score_result import ScoreResult
from services.export_service import ExportService


class ExportServiceTests(unittest.TestCase):
    def test_build_artifacts_includes_filters_ai_and_score_breakdown(self) -> None:
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator.",
            recent_content=["post one"],
            followers=42_000,
            language="English",
        )
        analysis = AIAnalysis(
            detected_language="English",
            niche="Fashion",
            government_support_score=77,
            political_orientation="supportive",
            confidence=0.88,
            summary="Aligned with public initiatives.",
            keywords=["fashion", "creator"],
            reasoning="Mentions public collaborations.",
        )
        score_result = ScoreResult(
            total_score=91.5,
            score_breakdown={"language": 20.0, "niche": 25.0, "ai_orientation": 12.5},
            matched_languages=["english"],
            matched_niches=["fashion"],
            remarks=["remark"],
        )
        result = EvaluatedInfluencer(influencer=influencer, ai_analysis=analysis, score_result=score_result, rank=1)
        filters = DashboardFilters(
            platform="Instagram",
            language="English",
            niche="Fashion",
            min_followers=1000,
            min_score=50.0,
            search_query="alice",
        )

        artifacts = ExportService().build_artifacts([result], filters)

        csv_df = pd.read_csv(BytesIO(artifacts.csv_bytes))
        self.assertEqual(list(csv_df["Name"]), ["Alice"])
        self.assertEqual(list(csv_df["Applied Platform Filter"]), ["Instagram"])
        self.assertIn("AI Summary", csv_df.columns)
        self.assertIn("Score Breakdown JSON", csv_df.columns)
        self.assertTrue(artifacts.csv_filename.endswith(".csv"))
        self.assertTrue(artifacts.excel_filename.endswith(".xlsx"))
        self.assertIn("T", artifacts.timestamp)

        excel_file = pd.ExcelFile(BytesIO(artifacts.excel_bytes))
        self.assertIn("Ranked Results", excel_file.sheet_names)
        self.assertIn("Export Metadata", excel_file.sheet_names)
