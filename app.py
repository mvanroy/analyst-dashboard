"""Root entrypoint for Igby Central.

The Daily Log is the production landing page. Trading tools remain available
from their direct routes and the reduced shared navigation.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Buggins Daily Log", layout="wide")
st.switch_page("pages/7_Boys_Log.py")
