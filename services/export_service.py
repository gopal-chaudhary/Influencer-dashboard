"""Export utilities for ranked influencer results.

This service converts evaluated dashboard results into CSV and Excel outputs
without depending on Streamlit so it can be reused in tests or future APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Sequence

import pandas as pd

from models import DashboardFilters, EvaluatedInfluencer


@dataclass(slots=True)
class ExportArtifacts:
    """Hold export payloads and their suggested filenames."""

    csv_bytes: bytes
    excel_bytes: bytes
    csv_filename: str
    excel_filename: str
    timestamp: str


class ExportService:
    """Build CSV and Excel exports for filtered, ranked influencer results."""

    def build_artifacts(
        self,
        evaluated_influencers: Sequence[EvaluatedInfluencer],
        filters: DashboardFilters,
    ) -> ExportArtifacts:
        """Create timestamped export payloads for the current dashboard view."""
        timestamp = self._build_timestamp()
        dataframe = self._build_export_dataframe(evaluated_influencers, filters, timestamp)
        csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
        excel_bytes = self._build_excel_bytes(dataframe, filters, timestamp)

        suffix = timestamp.replace(":", "").replace("-", "")
        return ExportArtifacts(
            csv_bytes=csv_bytes,
            excel_bytes=excel_bytes,
            csv_filename=f"influencer_rankings_{suffix}.csv",
            excel_filename=f"influencer_rankings_{suffix}.xlsx",
            timestamp=timestamp,
        )

    def _build_export_dataframe(
        self,
        evaluated_influencers: Sequence[EvaluatedInfluencer],
        filters: DashboardFilters,
        timestamp: str,
    ) -> pd.DataFrame:
        """Flatten the dashboard results into a tabular export shape."""
        rows = [self._build_row(result, filters, timestamp) for result in evaluated_influencers]
        return pd.DataFrame(rows)

    def _build_row(
        self,
        result: EvaluatedInfluencer,
        filters: DashboardFilters,
        timestamp: str,
    ) -> dict[str, object]:
        """Build one export row containing AI analysis, scoring, and filters."""
        ai_analysis = result.ai_analysis
        score_result = result.score_result
        influencer = result.influencer

        row: dict[str, object] = {
            "Export Timestamp": timestamp,
            "Rank": result.rank,
            "Name": influencer.name,
            "Handle": f"@{influencer.handle}",
            "Platform": influencer.platform,
            "Followers": influencer.followers,
            "Influencer Language": influencer.language,
            "Detected Language": ai_analysis.detected_language,
            "Niche": ai_analysis.niche,
            "Government Support Score": ai_analysis.government_support_score,
            "Political Orientation": ai_analysis.political_orientation,
            "Confidence": ai_analysis.confidence,
            "Total Score": score_result.total_score,
            "AI Summary": ai_analysis.summary,
            "AI Reasoning": ai_analysis.reasoning,
            "AI Keywords": ", ".join(ai_analysis.keywords),
            "Score Breakdown JSON": json.dumps(score_result.score_breakdown, ensure_ascii=False),
            "Applied Platform Filter": filters.platform or "All",
            "Applied Language Filter": filters.language or "All",
            "Applied Niche Filter": filters.niche or "All",
            "Minimum Followers Filter": filters.min_followers,
            "Minimum Score Filter": filters.min_score,
            "Search Query": filters.search_query,
        }

        for criterion, contribution in score_result.score_breakdown.items():
            row[f"Score - {criterion.replace('_', ' ').title()}"] = contribution

        return row

    def _build_excel_bytes(self, dataframe: pd.DataFrame, filters: DashboardFilters, timestamp: str) -> bytes:
        """Build an Excel workbook with results and filter metadata sheets."""
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Ranked Results")
            metadata = pd.DataFrame(
                [
                    {"Field": "Export Timestamp", "Value": timestamp},
                    {"Field": "Platform Filter", "Value": filters.platform or "All"},
                    {"Field": "Language Filter", "Value": filters.language or "All"},
                    {"Field": "Niche Filter", "Value": filters.niche or "All"},
                    {"Field": "Minimum Followers Filter", "Value": filters.min_followers},
                    {"Field": "Minimum Score Filter", "Value": filters.min_score},
                    {"Field": "Search Query", "Value": filters.search_query},
                    {"Field": "Rows Exported", "Value": len(dataframe.index)},
                ]
            )
            metadata.to_excel(writer, index=False, sheet_name="Export Metadata")
        return output.getvalue()

    @staticmethod
    def _build_timestamp() -> str:
        """Return a UTC timestamp suitable for exports and filenames."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
