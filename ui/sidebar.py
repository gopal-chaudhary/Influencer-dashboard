"""Sidebar content for the Streamlit UI."""

from __future__ import annotations

import streamlit as st

from repositories.influencer_repository import LoadResult


def _dataset_status(result: LoadResult | None) -> str:
    """Return a human-readable dataset status string."""
    if result is None:
        return "No dataset loaded"

    if result.loaded_count == 0:
        return "Loaded, but no valid influencers were found"

    if result.duplicate_count or result.invalid_count:
        return "Loaded with warnings"

    return "Ready"


def render_sidebar(result: LoadResult | None) -> None:
    """Render sidebar metadata about the current dataset."""
    with st.sidebar:
        st.title("Dataset status")

        total_influencers = result.loaded_count if result is not None else 0
        st.metric("Total influencers", total_influencers)

        st.markdown("### Supported file types")
        st.markdown("- CSV (`.csv`)")
        st.markdown("- Excel (`.xlsx`)")

        st.markdown("### Current dataset status")
        st.info(_dataset_status(result))

        if result is not None:
            st.caption(f"Rows processed: {result.total_rows}")
            st.caption(f"Duplicate rows removed: {result.duplicate_count}")
            st.caption(f"Invalid rows skipped: {result.invalid_count}")
