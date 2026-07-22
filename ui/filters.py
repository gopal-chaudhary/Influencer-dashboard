"""Sidebar filters for the ranked influencer dashboard."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import streamlit as st

from models import DashboardFilters, EvaluatedInfluencer


ALL_OPTION = "All"


def render_filters_sidebar(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> DashboardFilters:
    """Render dashboard filters in the Streamlit sidebar."""
    with st.sidebar:
        st.markdown("---")
        st.header("Filters")

        platforms = _build_options(result.influencer.platform for result in evaluated_influencers)
        languages = _build_options(result.ai_analysis.detected_language for result in evaluated_influencers)
        niches = _build_options(result.ai_analysis.niche for result in evaluated_influencers)

        platform = st.selectbox("Platform", [ALL_OPTION, *platforms], key="dashboard_platform_filter")
        language = st.selectbox("Language", [ALL_OPTION, *languages], key="dashboard_language_filter")
        niche = st.selectbox("Niche", [ALL_OPTION, *niches], key="dashboard_niche_filter")

        max_followers = max((result.influencer.followers for result in evaluated_influencers), default=0)
        min_followers = st.number_input(
            "Minimum followers",
            min_value=0,
            max_value=max_followers if max_followers > 0 else 0,
            value=0,
            step=100,
            key="dashboard_min_followers_filter",
        )

        min_score = st.slider(
            "Minimum score",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            key="dashboard_min_score_filter",
        )

        search_query = st.text_input(
            "Search name or handle",
            value="",
            key="dashboard_search_filter",
            placeholder="Search by name or @handle",
        )

    return DashboardFilters(
        platform=None if platform == ALL_OPTION else platform,
        language=None if language == ALL_OPTION else language,
        niche=None if niche == ALL_OPTION else niche,
        min_followers=int(min_followers),
        min_score=float(min_score),
        search_query=search_query,
    )


def _build_options(values: Iterable[str]) -> list[str]:
    """Return unique sorted filter options while skipping blanks."""
    cleaned_values = {value.strip() for value in values if value and value.strip()}
    return sorted(cleaned_values, key=str.casefold)
