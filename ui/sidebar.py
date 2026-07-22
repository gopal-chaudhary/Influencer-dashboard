"""Sidebar content for the Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config.gemini_config import GrokConfig
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
    """Render sidebar metadata about the current dataset and API configuration."""
    with st.sidebar:
        st.title("Configuration")
        
        # API Key Configuration
        st.markdown("### Gemini API Key")
        st.caption("Provide your own API key to avoid quota limits.")
        
        api_key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("gemini_api_key", ""),
            type="password",
            key="api_key_input",
            help="Leave empty to use environment variable (GEMINI_API_KEY or GOOGLE_API_KEY)",
        )
        
        if api_key_input:
            st.session_state["gemini_api_key"] = api_key_input
            st.success("✓ API key configured")
        elif st.session_state.get("gemini_api_key"):
            st.info("Using previously entered API key")
        else:
            default_config = GrokConfig.from_env()
            if default_config.has_api_key:
                st.success("✓ Using environment variable API key")
            else:
                st.warning("No API key configured. AI analysis will be skipped.")
        
        st.divider()
        st.markdown("### Dataset status")

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
