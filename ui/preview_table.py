"""Preview table for loaded influencer data."""

from __future__ import annotations

from typing import Sequence

import pandas as pd
import streamlit as st

from models import Influencer


MAX_PREVIEW_ROWS = 100


def render_preview_table(influencers: Sequence[Influencer]) -> None:
    """Render a preview table for the loaded influencers.

    The UI displays a flattened, human-readable version of the domain objects so
    users can confirm that the ingestion step parsed the file correctly.
    """
    st.subheader("Preview")

    if not influencers:
        st.info("No valid influencers were found in the uploaded dataset.")
        return

    dataframe = pd.DataFrame([influencer.to_dict() for influencer in influencers])
    if "recent_content" in dataframe.columns:
        dataframe["recent_content"] = dataframe["recent_content"].apply(
            lambda value: " | ".join(value) if isinstance(value, list) else str(value)
        )

    st.dataframe(dataframe.head(MAX_PREVIEW_ROWS), use_container_width=True, hide_index=True)
