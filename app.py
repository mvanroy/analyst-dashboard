"""Root entrypoint for the standalone Igby Central trading app."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Igby Central Trading", layout="wide")
st.switch_page("pages/1_Trade_Setup.py")
