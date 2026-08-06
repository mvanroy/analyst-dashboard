"""Root entrypoint for the standalone Buggins production app."""
from __future__ import annotations

import os
import runpy


os.environ["BUGGINS_STANDALONE"] = "1"

# Execute the Buggins log as the root app. This avoids painting a temporary
# Streamlit page and then navigating to /Boys_Log during every cold start.
runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages", "7_Boys_Log.py"),
    run_name="__main__",
)
