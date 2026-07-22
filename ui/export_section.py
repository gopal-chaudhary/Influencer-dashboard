"""Download buttons for exporting dashboard results."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from models import DashboardFilters, EvaluatedInfluencer
from services.export_service import ExportService


def render_export_section(
    evaluated_influencers: Sequence[EvaluatedInfluencer],
    filters: DashboardFilters,
    export_service: ExportService,
) -> None:
    """Render CSV and Excel download buttons for the current dashboard view."""
    st.subheader("Export results")

    if not evaluated_influencers:
        st.info("No filtered results are available for export.")
        return

    artifacts = export_service.build_artifacts(evaluated_influencers, filters)
    st.caption(f"Export generated at {artifacts.timestamp} UTC")

    csv_col, excel_col = st.columns(2)
    csv_col.download_button(
        label="Download CSV",
        data=artifacts.csv_bytes,
        file_name=artifacts.csv_filename,
        mime="text/csv",
        use_container_width=True,
    )
    excel_col.download_button(
        label="Download Excel",
        data=artifacts.excel_bytes,
        file_name=artifacts.excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
