"""Root entrypoint for the standalone Buggins production app."""
from __future__ import annotations

import os

import streamlit as st

os.environ["BUGGINS_STANDALONE"] = "1"

st.set_page_config(page_title="Buggins Daily Log", layout="wide")
st.switch_page("pages/7_Boys_Log.py")
