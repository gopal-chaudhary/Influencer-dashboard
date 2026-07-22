"""Main dashboard renderer for evaluated influencers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
import streamlit as st

from models import DashboardFilters, EvaluatedInfluencer
from services.export_service import ExportService
from ui.export_section import render_export_section


TABLE_COLUMNS = [
    "Rank",
    "Name",
    "Handle",
    "Platform",
    "Followers",
    "Language",
    "Niche",
    "Government Support Score",
    "Total Score",
    "Confidence",
]


def render_dashboard(
    evaluated_influencers: Sequence[EvaluatedInfluencer],
    filters: DashboardFilters,
    export_service: ExportService,
) -> None:
    """Render the complete ranked dashboard for the current filtered results."""
    if not evaluated_influencers:
        st.info("No influencer analysis matches the current filters.")
        return

    _render_metrics(evaluated_influencers)
    _render_results_table(evaluated_influencers)
    render_export_section(evaluated_influencers, filters, export_service)
    _render_details(evaluated_influencers)


def _render_metrics(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> None:
    """Render dashboard summary metrics."""
    st.subheader("Dashboard overview")

    total_influencers = len(evaluated_influencers)
    average_score = _average_score(evaluated_influencers)
    highest_score = _highest_score(evaluated_influencers)
    languages = _unique_values(result.ai_analysis.detected_language for result in evaluated_influencers)
    platforms = _unique_values(result.influencer.platform for result in evaluated_influencers)

    columns = st.columns(5)
    columns[0].metric("Total influencers", total_influencers)
    columns[1].metric("Average score", f"{average_score:.1f}")
    columns[2].metric("Highest score", f"{highest_score:.1f}")
    columns[3].metric("Languages detected", len(languages))
    columns[4].metric("Platforms represented", len(platforms))

    if languages:
        st.caption(f"Languages: {', '.join(languages)}")
    if platforms:
        st.caption(f"Platforms: {', '.join(platforms)}")


def _render_results_table(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> None:
    """Render the main ranked table."""
    st.subheader("Ranked influencers")
    st.caption("Sorted by total score in descending order.")

    if not evaluated_influencers:
        st.info("No influencers match the current filters.")
        return

    dataframe = pd.DataFrame([_to_table_row(result) for result in evaluated_influencers])
    st.dataframe(dataframe[TABLE_COLUMNS], use_container_width=True, hide_index=True)


def _render_details(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> None:
    """Render expandable detail sections for each influencer."""
    st.subheader("View details")

    if not evaluated_influencers:
        return

    for result in evaluated_influencers:
        influencer = result.influencer
        ai_analysis = result.ai_analysis
        score_result = result.score_result
        with st.expander(f"#{result.rank} {influencer.name} (@{influencer.handle})", expanded=False):
            st.markdown(f"**Bio:** {influencer.bio or 'No bio provided.'}")
            st.markdown("**Recent content:**")
            if influencer.recent_content:
                for item in influencer.recent_content:
                    st.write(f"- {item}")
            else:
                st.write("- No recent content provided.")

            st.markdown(f"**AI summary:** {ai_analysis.summary or 'No summary available.'}")
            st.markdown(f"**AI reasoning:** {ai_analysis.reasoning or 'No reasoning available.'}")
            st.markdown(f"**Keywords:** {', '.join(ai_analysis.keywords) if ai_analysis.keywords else 'None'}")
            st.markdown("**Score breakdown:**")
            breakdown_df = pd.DataFrame(
                [
                    {"Criterion": criterion, "Contribution": contribution}
                    for criterion, contribution in score_result.score_breakdown.items()
                ]
            )
            st.dataframe(breakdown_df, hide_index=True, use_container_width=True)


def _to_table_row(result: EvaluatedInfluencer) -> dict[str, object]:
    """Convert an evaluated influencer into a single table row."""
    return {
        "Rank": result.rank,
        "Name": result.influencer.name,
        "Handle": f"@{result.influencer.handle}",
        "Platform": result.influencer.platform,
        "Followers": result.influencer.followers,
        "Language": result.ai_analysis.detected_language,
        "Niche": result.ai_analysis.niche,
        "Government Support Score": result.ai_analysis.government_support_score,
        "Total Score": result.score_result.total_score,
        "Confidence": result.ai_analysis.confidence,
    }


def _average_score(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> float:
    """Return the average total score for a list of results."""
    if not evaluated_influencers:
        return 0.0
    return sum(result.score_result.total_score for result in evaluated_influencers) / len(evaluated_influencers)


def _highest_score(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> float:
    """Return the highest total score in the list."""
    if not evaluated_influencers:
        return 0.0
    return max(result.score_result.total_score for result in evaluated_influencers)


def _unique_values(values: Iterable[str]) -> list[str]:
    """Return unique, trimmed values in a stable sorted order."""
    unique_values = {value.strip() for value in values if value and value.strip()}
    return sorted(unique_values, key=str.casefold)
