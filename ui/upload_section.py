"""Upload section for the Streamlit UI.

This component handles the file uploader and delegates all file parsing to the
repository layer.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from repositories.influencer_repository import InfluencerRepository, LoadResult
from utils.exceptions import IngestionError


SUPPORTED_FILE_TYPES: tuple[str, ...] = ("csv", "xlsx")


def render_upload_section(repository: InfluencerRepository) -> Optional[LoadResult]:
    """Render the upload widget and process the uploaded file.

    Args:
        repository: The data repository responsible for parsing and validation.

    Returns:
        A ``LoadResult`` when a file is successfully processed, otherwise
        ``None``.
    """
    st.header("Upload influencer dataset")
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=list(SUPPORTED_FILE_TYPES),
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info("Upload a CSV or XLSX file to preview influencers.")
        st.session_state.pop("dataset_result", None)
        return None

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    try:
        result = repository.load_with_stats(uploaded_file)
    except IngestionError as exc:
        st.session_state.pop("dataset_result", None)
        st.error(str(exc))
        return None

    st.session_state["dataset_result"] = result

    st.success("Dataset loaded successfully.")

    metrics = st.columns(3)
    metrics[0].metric("Influencers loaded", result.loaded_count)
    metrics[1].metric("Duplicate rows removed", result.duplicate_count)
    metrics[2].metric("Invalid rows", result.invalid_count)

    if result.duplicate_count or result.invalid_count:
        st.warning(
            "Some rows were skipped during validation. "
            "Review duplicates and invalid records before continuing."
        )

    return result
