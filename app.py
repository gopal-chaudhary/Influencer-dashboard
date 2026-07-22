"""Streamlit entrypoint for the Influencer Discovery Dashboard."""

from __future__ import annotations

import streamlit as st

from repositories.influencer_repository import InfluencerRepository
from ui.preview_table import render_preview_table
from ui.sidebar import render_sidebar
from ui.upload_section import render_upload_section


st.set_page_config(
    page_title="Influencer Discovery Dashboard",
    page_icon="",
    layout="wide",
)

st.title("Influencer Discovery Dashboard")
st.caption("Upload CSV or XLSX influencer datasets and preview the parsed records.")

repository = InfluencerRepository()

if "dataset_result" not in st.session_state:
    st.session_state["dataset_result"] = None

upload_result = render_upload_section(repository)
if upload_result is not None:
    st.session_state["dataset_result"] = upload_result

current_result = st.session_state.get("dataset_result")
render_sidebar(current_result)

if current_result is not None:
    render_preview_table(current_result.influencers)
else:
    st.info("Upload a dataset to display a preview table.")
