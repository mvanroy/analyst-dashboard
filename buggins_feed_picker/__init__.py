"""Supported Streamlit component for the Buggins native feed picker."""
from __future__ import annotations

from pathlib import Path
import re

import streamlit as st
import streamlit.components.v1 as components


_frontend = Path(__file__).resolve().parent / "frontend"
_picker = components.declare_component(
    "buggins_feed_picker",
    path=str(_frontend),
)

_source = (_frontend / "index.html").read_text(encoding="utf-8")
_style_match = re.search(r"<style>(.*?)</style>", _source, flags=re.DOTALL)
_v2_picker = (
    st.components.v2.component(
        "buggins_feed_picker_v2",
        html='<main id="app" aria-live="polite"></main>',
        css=_style_match.group(1) if _style_match else "",
        js=(_frontend / "v2.js").read_text(encoding="utf-8"),
        isolate_styles=True,
    )
    if hasattr(st.components, "v2")
    else None
)


def render_feed_picker(config: dict, *, key: str, on_event=None):
    """Render the native-select picker and return its latest action."""
    if _v2_picker is not None:
        result = _v2_picker(
            data=config,
            key=key,
            on_event_change=on_event or (lambda: None),
            height="content",
        )
        value = result.event
        if value is None or isinstance(value, dict):
            return value
        getter = getattr(value, "get", None)
        return {
            field: getter(field) if callable(getter) else getattr(value, field, None)
            for field in ("action", "payload", "nonce")
        }
    return _picker(config=config, key=key, default=None)
