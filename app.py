"""Root entrypoint.

The visible Scanner lives at /Scanner so the address bar matches the page label.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Scanner", layout="wide")
st.switch_page("pages/0_Scanner.py")
