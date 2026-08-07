"""Install the Buggins startup shell into Streamlit's static index."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil

import streamlit


MARKER = "<!-- buggins-shell-v9 -->"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    # Streamlit serves the project's static directory as browser-cacheable
    # files. Copy the established artwork there once when the container
    # starts instead of embedding it in every Streamlit delta.
    shutil.copytree(
        project_root / "assets",
        project_root / "static" / "buggins-assets",
        dirs_exist_ok=True,
    )
    configured_path = os.getenv("BUGGINS_STREAMLIT_INDEX", "").strip()
    index_path = (
        Path(configured_path)
        if configured_path
        else Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    )
    source = index_path.read_text(encoding="utf-8")
    if MARKER in source:
        return
    startup_script = (
        project_root / "static" / "buggins-startup.js"
    ).read_text(encoding="utf-8")

    head = f"""{MARKER}
    <title>Buggins Daily Log</title>
    <meta name="theme-color" content="#061326" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="Buggins" />
    <link rel="manifest" href="/app/static/manifest.webmanifest?v=9" />
    <link rel="apple-touch-icon" href="/app/static/apple-touch-icon.png?v=9" />
    <style id="buggins-startup-style">
      html, body {{ margin: 0; background: #061326 !important; }}
      body.buggins-loading {{ overflow: hidden !important; }}
      body.buggins-loading #root {{ visibility: hidden !important; }}
      #buggins-startup-shell {{
        position: fixed; inset: 0; z-index: 2147483647;
        display: block; background: #061326;
      }}
      body.buggins-ready #buggins-startup-shell {{ display: none; }}
    </style>"""
    if not re.search(r"<title>.*?</title>", source, flags=re.DOTALL | re.IGNORECASE):
        raise RuntimeError(f"Unsupported Streamlit index template: {index_path}")
    source = re.sub(
        r"<title>.*?</title>",
        head,
        source,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    source, body_replacements = re.subn(
        r"<body(?:\s[^>]*)?>",
        '<body class="buggins-loading"><div id="buggins-startup-shell" aria-hidden="true"></div>',
        source,
        count=1,
        flags=re.IGNORECASE,
    )
    if body_replacements != 1:
        raise RuntimeError(f"Unsupported Streamlit body template: {index_path}")
    source = source.replace(
        "</body>",
        f"<script>\n{startup_script}\n</script></body>",
        1,
    )
    index_path.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
