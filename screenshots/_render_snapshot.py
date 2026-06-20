"""Render the Trade Dashboard to a standalone static HTML file for screenshotting.

Builds the exact markup the Streamlit app produces (from analyses/<SYMBOL>.json +
a live Binance quote), wrapped with the brand header. Static => renders instantly
in headless Chrome, so the full dashboard is captured reliably.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chrome
import dashboard
import scanner

symbol = (sys.argv[1] if len(sys.argv) > 1 else "HYPEUSDT").upper()
with open(f"analyses/{symbol}.json") as f:
    d = json.load(f)

try:
    q = scanner.live_ticker(symbol)
except Exception:
    q = None

dash_html = dashboard._dash(
    dashboard._dhead_top(d, q) + dashboard._dhead_bottom(d) + dashboard._body_rows(d)
)

logo = chrome.logo_data_uri()
brand = (
    '<div class="orion-brand">'
    + (f'<img src="{logo}" alt="logo">' if logo else "")
    + '<div class="orion-logo">TRADE <span class="accent">DASHBOARD</span></div>'
    + "</div>"
)

page = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
    "body{margin:0;background:#0b0e11;padding:26px 30px;"
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}'
    ".orion-brand{display:flex;align-items:center;gap:.7rem;margin:0 0 20px 0;}"
    ".orion-brand img{width:54px;height:54px;}"
    ".orion-logo{font-size:1.7rem;font-weight:800;letter-spacing:.04em;color:#e6e8eb;}"
    ".orion-logo .accent{color:#4c8dff;}"
    "</style></head><body>" + brand + dash_html + "</body></html>"
)

out = "screenshots/_dash_render.html"
with open(out, "w") as f:
    f.write(page)
print("wrote", out, "len", len(page))
