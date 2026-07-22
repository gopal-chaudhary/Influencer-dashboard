"""Streamlit entrypoint for the Influencer Discovery Dashboard."""

from __future__ import annotations

import hashlib
import json

import streamlit as st

from config.gemini_config import GeminiConfig
from config.scoring_config import ScoringConfig
from repositories.influencer_repository import InfluencerRepository
from services.dashboard_service import DashboardWorkflowService
from services.export_service import ExportService
from services.gemini_service import GeminiConfigurationError, GeminiService
from services.scoring_service import ScoringService
from ui.dashboard import render_dashboard
from ui.filters import render_filters_sidebar
from ui.sidebar import render_sidebar
from ui.upload_section import render_upload_section
from utils import configure_logging, get_logger


def _fingerprint_influencers(influencers) -> str:
    """Build a stable fingerprint for the current dataset."""
    payload = json.dumps([influencer.to_dict() for influencer in influencers], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


configure_logging()
logger = get_logger(__name__)


st.set_page_config(
    page_title="Influencer Discovery Dashboard",
    page_icon="",
    layout="wide",
)

st.title("Influencer Discovery Dashboard")
st.caption("Upload a CSV or XLSX dataset to analyze, rank, and explore influencers.")

repository = InfluencerRepository()

st.session_state.setdefault("dataset_result", None)
st.session_state.setdefault("evaluated_influencers", None)
st.session_state.setdefault("dataset_fingerprint", None)
st.session_state.setdefault("workflow_error", None)

try:
    upload_result = render_upload_section(repository)
    if upload_result is not None:
        st.session_state["dataset_result"] = upload_result

    current_result = st.session_state.get("dataset_result")
    render_sidebar(current_result)

    if current_result is None:
        st.info("Upload a dataset to begin the analysis workflow.")
        st.stop()

    fingerprint = _fingerprint_influencers(current_result.influencers)
    needs_refresh = (
        st.session_state.get("dataset_fingerprint") != fingerprint
        or st.session_state.get("evaluated_influencers") is None
    )

    if needs_refresh:
        try:
            # Create workflow service with custom API key if provided
            api_key = st.session_state.get("gemini_api_key")
            if api_key:
                # Use custom API key
                custom_config = GeminiConfig.with_api_key(api_key)
                gemini_service = GeminiService(config=custom_config)
                workflow_service = DashboardWorkflowService(
                    gemini_service=gemini_service,
                    scoring_service=ScoringService(ScoringConfig()),
                )
            else:
                # Use default configuration (from environment or .env)
                workflow_service = DashboardWorkflowService.create_default()
        except GeminiConfigurationError as exc:
            st.session_state["workflow_error"] = str(exc)
            logger.error("Unable to create workflow service: %s", exc)
            st.error(str(exc))
            st.stop()

        with st.spinner("Analyzing influencers with Gemini and scoring the results..."):
            st.session_state["evaluated_influencers"] = workflow_service.evaluate_influencers(current_result.influencers)
            st.session_state["dataset_fingerprint"] = fingerprint
            st.session_state["workflow_error"] = None

    if st.session_state.get("workflow_error"):
        st.error(st.session_state["workflow_error"])
        st.stop()

    all_evaluated_influencers = st.session_state.get("evaluated_influencers") or []
    filters = render_filters_sidebar(all_evaluated_influencers)
    filtered_evaluations = DashboardWorkflowService.filter_results(all_evaluated_influencers, filters)

    export_service = ExportService()
    render_dashboard(filtered_evaluations, filters, export_service)
except Exception as exc:  # pragma: no cover - defensive UI guard
    logger.exception("Unexpected dashboard failure")
    st.error("An unexpected error occurred while rendering the dashboard.")
    st.caption(str(exc))
