"""Trade Setup — single-coin read rendered from a structured analysis
file (analyses/<SYMBOL>.json) produced by the Trade Setup Framework
(framework/trade_setup_framework.md) via /trade + /push-dashboard.

The Market Scanner in app.py is untouched; this page is fully isolated.
"""
from __future__ import annotations

import html
import json
import base64
import os
import re
import time

import streamlit as st

import chrome
import dashboard
import openai_analysis

st.set_page_config(page_title="Trade Setup", page_icon="📊", layout="wide")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
RUNTIME_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
CHART_UPLOAD_DIR = os.path.join(RUNTIME_DIR, "uploaded_charts")
FILTER_ICON_PATH = os.path.join(ASSETS_DIR, "filter.svg")
SEARCH_ICON_PATH = os.path.join(ASSETS_DIR, "cryptocurrency.svg")
PROMPT_ICON_PATH = os.path.join(ASSETS_DIR, "prompt.svg")
AI_ICON_PATH = os.path.join(ASSETS_DIR, "ai.svg")
UPLOAD_ICON_PATH = os.path.join(ASSETS_DIR, "upload.svg")
FILE_UPLOAD_ICON_PATH = os.path.join(ASSETS_DIR, "file-upload.svg")


def _icon_data_uri(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


_FILTER_ICON_URI = _icon_data_uri(FILTER_ICON_PATH)
_SEARCH_ICON_URI = _icon_data_uri(SEARCH_ICON_PATH)
_PROMPT_ICON_URI = _icon_data_uri(PROMPT_ICON_PATH)
_AI_ICON_URI = _icon_data_uri(AI_ICON_PATH)
_UPLOAD_ICON_URI = _icon_data_uri(UPLOAD_ICON_PATH)
_FILE_UPLOAD_ICON_URI = _icon_data_uri(FILE_UPLOAD_ICON_PATH)

# Shared chrome: nav + live clocks row (brand rendered below alongside the
# ticker analysis controls).
chrome.render_header("TRADE", "SETUP", brand=False)

# Brand + ticker analysis controls on one row.
st.markdown(
    "<style>"
    # Ambient purple gradient behind the cards — shared with the Market Scanner and
    # Position Calculator. Folded into this one <style> (rather than a separate
    # inject_background() markdown) so the element count before the brand row is
    # unchanged and the heading stays vertically aligned with the other pages.
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + "[data-testid='stMain'],[data-testid='stMainBlockContainer']{background:transparent!important;}"
    # This page puts nothing in the sidebar (page-nav is hidden, no Settings), so the
    # empty panel is just confusing dead space — and chrome.py hides stHeader, which
    # removes the only control to reopen it once collapsed. Hide it outright here.
    + "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none!important;}"
    ".st-key-brandrow{display:block!important;position:relative!important;height:108px!important;min-height:108px!important;margin-bottom:8px;}"
    ".st-key-brandrow > [data-testid='stElementContainer'],.st-key-brandrow > [class*='st-emotion-cache']{position:absolute!important;}"
    ".st-key-brandrow > :nth-child(1){left:0;top:0;width:176px;}"
    ".st-key-brandrow > :nth-child(2){left:0;top:58px;width:130px;}"
    ".st-key-brandrow > :nth-child(3){left:142px;top:58px;width:235px;}"
    ".st-key-brandrow > :nth-child(4){left:389px;top:58px;width:230px;}"
    ".st-key-brandrow > :nth-child(5){left:631px;top:58px;width:118px;}"
    ".st-key-brandrow > :nth-child(6){display:none!important;}"
    ".st-key-brandrow > :nth-child(7){right:0;top:58px;width:134px;}"
    ".st-key-brandrow .stTextInput{width:130px!important;transform:none!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement']{height:32px!important;"
    "border-radius:7px!important;border:1px solid rgba(230,232,235,.22)!important;"
    "background:rgba(10,14,20,.42)!important;box-shadow:none!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement']:focus-within{"
    "border-color:#4c8dff!important;box-shadow:0 0 0 1px rgba(76,141,255,.14)!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement'] > div{"
    "background:transparent!important;height:100%!important;}"
    ".st-key-brandrow .stTextInput input{height:100%!important;border:0!important;"
    "border-radius:0!important;background:transparent!important;color:#e6e8eb!important;"
    "font-size:.82rem!important;padding:0.25rem .85rem!important;text-transform:uppercase;}"
    ".st-key-brandrow .stTextInput input:focus{box-shadow:none!important;outline:none!important;}"
    ".st-key-analysis_setup_chart{transform:none;}"
    ".st-key-analysis_setup_chart [data-testid='stWidgetLabel']{display:none!important;}"
    ".st-key-analysis_setup_chart [data-testid='stPills']{display:flex;gap:.28rem;flex-wrap:nowrap!important;}"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button{min-height:32px!important;"
    "border-radius:7px!important;border:1px solid rgba(230,232,235,.18)!important;"
    "background:rgba(10,14,20,.30)!important;color:#8b94a0!important;font-size:.76rem!important;"
    "font-weight:800!important;padding:.18rem .58rem!important;}"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button:hover{"
    "border-color:rgba(76,141,255,.55)!important;color:#dce3ec!important;}"
    ".st-key-analysis_setup_chart button[data-testid='stBaseButton-pillsActive'],"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button[aria-pressed='true'],"
    ".st-key-analysis_setup_chart [data-testid='stPills'] button[aria-selected='true']{"
    "border-color:#4c6fff!important;background:rgba(76,111,255,.14)!important;"
    "color:#587dff!important;box-shadow:inset 0 0 0 1px #4c6fff,0 0 16px rgba(76,111,255,.18)!important;}"
    ".st-key-promptseg{flex-direction:row!important;gap:0!important;width:118px!important;align-items:stretch!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']{flex:1 1 0!important;width:auto!important;min-width:0!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']:nth-child(1) button{border-radius:7px 0 0 7px!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']:nth-child(2){margin-left:-1px!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']:nth-child(2) button{border-radius:0 7px 7px 0!important;}"
    ".st-key-promptseg button{width:100%!important;min-height:0!important;font-size:12px!important;"
    "letter-spacing:.02em;padding:.34rem .4rem!important;white-space:nowrap!important;transition:none!important;"
    "border:1px solid #2a323c!important;background:transparent!important;color:#8b94a0!important;"
    "display:flex!important;align-items:center!important;justify-content:center!important;gap:6px!important;}"
    ".st-key-promptseg button p{line-height:1!important;margin:0!important;white-space:nowrap!important;}"
    ".st-key-segprompt_on button p,.st-key-segprompt_off button p{display:none!important;}"
    ".st-key-promptseg [class*='seg'][class*='_off'] button{background:transparent!important;color:#8b94a0!important;font-weight:600!important;}"
    ".st-key-promptseg [class*='seg'][class*='_off'] button:hover{color:#cdd3da!important;border-color:#3a4250!important;background:rgba(255,255,255,.02)!important;}"
    ".st-key-promptseg [class*='seg'][class*='_on'] button{position:relative!important;z-index:2!important;font-weight:800!important;}"
    ".st-key-segprompt_on button,.st-key-segprompt_on button:hover,"
    ".st-key-segai_on button,.st-key-segai_on button:hover{background:rgba(76,141,255,.14)!important;border-color:#4c8dff!important;color:#4c8dff!important;}"
    ".st-key-segprompt_on button::before,.st-key-segprompt_off button::before,"
    ".st-key-segai_on button::before,.st-key-segai_off button::before{content:'';display:inline-block;width:16px;height:16px;flex:0 0 16px;background:currentColor;}"
    f".st-key-segprompt_on button::before,.st-key-segprompt_off button::before{{-webkit-mask:url('{_PROMPT_ICON_URI}') center/contain no-repeat;mask:url('{_PROMPT_ICON_URI}') center/contain no-repeat;}}"
    f".st-key-segai_on button::before,.st-key-segai_off button::before{{-webkit-mask:url('{_AI_ICON_URI}') center/contain no-repeat;mask:url('{_AI_ICON_URI}') center/contain no-repeat;}}"
    ".st-key-analysebtn{display:flex!important;justify-content:flex-end!important;width:100%!important;}"
    ".st-key-analysebtn button{border-radius:9999px;border:1px solid rgba(76,141,255,.75)!important;"
    "background:rgba(76,141,255,.12)!important;color:#e6e8eb!important;font-weight:600;"
    "min-height:0;padding:0.25rem 0.9rem;width:auto;white-space:nowrap;transform:none;}"
    ".st-key-analysebtn button:hover{border-color:#4c8dff!important;color:#4c8dff!important;"
    "background:transparent!important;}"
    ".st-key-chartupload{width:230px!important;max-width:230px!important;margin:0;padding:0;background:transparent!important;}"
    ".st-key-chartupload > [data-testid='stElementContainer'],.st-key-chartupload [data-testid='stFileUploader'],"
    ".st-key-chartupload [data-testid='stFileUploader'] > div{width:100%!important;max-width:100%!important;}"
    ".st-key-chartupload [data-testid='stFileUploader']{position:relative!important;height:32px!important;}"
    ".st-key-chartupload [data-testid='stWidgetLabel']{display:none!important;}"
    ".st-key-chartupload [data-testid='stFileUploader']{width:100%!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']{height:32px!important;min-height:32px!important;"
    "padding:0!important;position:relative!important;display:flex!important;align-items:center!important;"
    "border:1px solid rgba(139,92,246,.38)!important;border-radius:9px!important;"
    "background:rgba(18,28,40,.72)!important;overflow:hidden!important;"
    "box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15)!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']::before{content:'UPLOAD CHART';"
    "position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#8b94a0;font-size:.9rem;"
    "font-weight:400;letter-spacing:0;line-height:1;pointer-events:none;font-family:inherit;text-transform:uppercase;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']::after{content:'';position:absolute;right:14px;top:50%;"
    "width:22px;height:22px;transform:translateY(-50%);background:#8b94a0;pointer-events:none;"
    f"-webkit-mask:url('{_UPLOAD_ICON_URI}') center/contain no-repeat;mask:url('{_UPLOAD_ICON_URI}') center/contain no-repeat;}}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']:active::after,"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']:focus-within::after{"
    f"-webkit-mask:url('{_FILE_UPLOAD_ICON_URI}') center/contain no-repeat;mask:url('{_FILE_UPLOAD_ICON_URI}') center/contain no-repeat;}}"
    ".st-key-chartupload:has([data-testid='stFileUploaderFile']) [data-testid='stFileUploaderDropzone']::before,"
    ".st-key-chartupload:has([data-testid='stFileUploaderFile']) [data-testid='stFileUploaderDropzone']::after{display:none!important;content:''!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone'] [data-testid='stFileUploaderDropzoneInstructions'],"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone'] small{display:none!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone'] button{position:absolute!important;inset:0!important;"
    "width:100%!important;height:100%!important;border:0!important;background:transparent!important;"
    "color:transparent!important;padding:0!important;z-index:2!important;box-shadow:none!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']:hover{border-color:rgba(139,92,246,.58)!important;"
    "background:rgba(18,28,40,.82)!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFile']{position:absolute!important;left:13px!important;right:9px!important;top:0!important;"
    "height:32px!important;min-height:32px!important;margin:0!important;padding:0 30px 0 0!important;z-index:3!important;"
    "border:0!important;background:transparent!important;box-shadow:none!important;overflow:hidden!important;display:flex!important;align-items:center!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFile'] > svg{display:none!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFile'] *{max-width:100%!important;min-width:0!important;overflow:hidden!important;"
    "text-overflow:ellipsis!important;white-space:nowrap!important;color:#cdd3da!important;font-size:.82rem!important;line-height:1!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFileDeleteButton']{position:absolute!important;right:0!important;top:50%!important;"
    "width:26px!important;height:26px!important;min-height:26px!important;border-radius:999px!important;"
    "transform:translateY(-50%)!important;z-index:4!important;color:#8b94a0!important;background:transparent!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFileDeleteButton'] svg{display:block!important;width:15px!important;height:15px!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderFileDeleteButton']:hover{color:#cdd3da!important;background:rgba(255,255,255,.04)!important;}"
    ".st-key-mobilefilterbtn{display:none;}"
    "@media (max-width:700px){"
    ".st-key-brandrow{display:block!important;position:relative!important;height:126px!important;margin-top:-18px!important;min-height:126px!important;"
    "padding:0 0 6px!important;}"
    ".st-key-brandrow > :nth-child(1){display:none!important;}"
    ".st-key-brandrow > :nth-child(2){left:0!important;top:0!important;width:calc(44% - 4px)!important;}"
    ".st-key-brandrow > :nth-child(3){left:calc(44% + 4px)!important;right:0!important;top:0!important;width:auto!important;}"
    ".st-key-brandrow > :nth-child(4){left:0!important;right:0!important;top:49px!important;width:auto!important;}"
    ".st-key-brandrow > :nth-child(5){left:0!important;top:99px!important;width:118px!important;max-width:118px!important;}"
    ".st-key-brandrow > :nth-child(6){display:none!important;}"
    ".st-key-brandrow > :nth-child(7){right:0!important;top:98px!important;width:134px!important;}"
    ".st-key-brandrow [data-testid='stElementContainer']{align-self:center!important;min-width:0!important;}"
    ".st-key-brandrow .stTextInput{width:100%!important;transform:none!important;}"
    ".st-key-brandrow .stTextInput [data-testid='stTextInputRootElement']{height:42px!important;"
    "border-radius:10px!important;border-color:rgba(139,92,246,.38)!important;"
    "background:rgba(18,28,40,.72)!important;position:relative!important;"
    "box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15)!important;}"
    ".st-key-brandrow .stTextInput input{font-size:.9rem!important;padding:.35rem .75rem!important;"
    "text-transform:uppercase;}"
    ".st-key-brandrow .stTextInput input::placeholder{text-transform:uppercase!important;color:#8b94a0!important;}"
    ".st-key-brandrow [data-testid='InputInstructions'],"
    ".st-key-brandrow [data-testid='stTextInput'] [data-testid='InputInstructions']{display:none!important;}"
    ".st-key-analysis_setup_chart{grid-column:2!important;grid-row:1!important;transform:none!important;width:100%!important;"
    "position:relative!important;margin-top:0!important;}"
    ".st-key-analysis_setup_chart [data-testid='stButtonGroup']{width:100%!important;}"
    ".st-key-analysis_setup_chart [role='radiogroup']{display:grid!important;width:100%!important;"
    "grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:3px!important;padding:3px!important;"
    "min-height:42px!important;border:1px solid rgba(139,92,246,.38);border-radius:10px;"
    "background:rgba(18,28,40,.72);box-shadow:0 0 0 1px rgba(124,58,237,.06),0 0 22px rgba(124,58,237,.15);overflow:hidden;}"
    ".st-key-analysis_setup_chart [role='radiogroup'] button{width:100%!important;height:34px!important;"
    "min-height:34px!important;border:0!important;border-radius:7px!important;background:transparent!important;"
    "box-shadow:none!important;font-size:.72rem!important;font-weight:740!important;color:#cdd3da!important;"
    "padding:0!important;}"
    ".st-key-analysis_setup_chart [role='radiogroup'] button:hover{background:rgba(255,255,255,.035)!important;"
    "color:#f2f4f8!important;}"
    ".st-key-analysis_setup_chart button[data-testid='stBaseButton-pillsActive'],"
    ".st-key-analysis_setup_chart [role='radiogroup'] button[aria-pressed='true'],"
    ".st-key-analysis_setup_chart [role='radiogroup'] button[aria-selected='true']{"
    "background:rgba(76,111,255,.14)!important;color:#587dff!important;"
    "box-shadow:inset 0 0 0 1px #4c6fff,0 0 16px rgba(76,111,255,.18)!important;}"
    ".st-key-brandrow [data-testid='stElementContainer']:has(.st-key-chartupload){grid-column:1 / span 2!important;grid-row:2!important;"
    "width:100%!important;min-width:0!important;align-self:stretch!important;}"
    ".st-key-brandrow [data-testid='stLayoutWrapper']:has(.st-key-promptseg){grid-column:1!important;grid-row:3!important;"
    "width:118px!important;max-width:118px!important;min-width:0!important;align-self:center!important;}"
    ".st-key-brandrow [data-testid='stElementContainer']:has(.st-key-promptseg){grid-column:1!important;grid-row:3!important;"
    "width:118px!important;max-width:118px!important;min-width:0!important;align-self:center!important;}"
    ".st-key-promptseg{grid-column:1!important;grid-row:3!important;width:100%!important;max-width:100%!important;min-width:0!important;"
    "align-self:stretch!important;position:relative!important;gap:0!important;align-items:stretch!important;"
    "border:1px solid #2b3140!important;border-radius:999px!important;overflow:hidden!important;background:rgba(8,10,22,.22)!important;}"
    ".st-key-promptseg button{height:34px!important;min-height:34px!important;font-size:8px!important;"
    "padding:0 .18rem!important;letter-spacing:0!important;font-weight:660!important;"
    "border:0!important;background:transparent!important;color:#8f96a3!important;gap:4px!important;}"
    ".st-key-promptseg button::before{width:18px!important;height:18px!important;flex-basis:18px!important;}"
    ".st-key-segprompt_on button,.st-key-segprompt_off button{gap:0!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']:nth-child(1) button{border-radius:999px 0 0 999px!important;}"
    ".st-key-promptseg > [data-testid='stElementContainer']:nth-child(2) button{border-radius:0 999px 999px 0!important;}"
    ".st-key-segprompt_on button,.st-key-segprompt_on button:hover,"
    ".st-key-segai_on button,.st-key-segai_on button:hover{background:rgba(76,111,255,.14)!important;"
    "box-shadow:inset 0 0 0 1px #4c6fff,0 0 16px rgba(76,111,255,.18)!important;color:#587dff!important;}"
    ".st-key-analysebtn{display:block!important;grid-column:3!important;grid-row:3!important;"
    "justify-self:stretch!important;align-self:center!important;width:100%!important;z-index:5!important;"
    "display:flex!important;justify-content:flex-end!important;pointer-events:none!important;}"
    ".st-key-analysebtn [data-testid='stButton']{width:134px!important;margin-left:auto!important;pointer-events:none!important;}"
    ".st-key-analysebtn button{width:134px!important;height:38px!important;min-height:38px!important;transform:none!important;"
    "border:1px solid #4c6fff!important;border-radius:999px!important;background:rgba(76,111,255,.14)!important;padding:0 10px 0 13px!important;"
    "box-shadow:none!important;"
    "display:flex!important;align-items:center!important;justify-content:center!important;gap:8px!important;pointer-events:auto!important;}"
    ".st-key-analysebtn button p{font-size:.9rem!important;line-height:1!important;margin:0!important;font-weight:400!important;"
    "letter-spacing:0!important;text-transform:uppercase!important;color:#587dff!important;order:1!important;}"
    ".st-key-analysebtn button::before{content:'';width:24px;height:24px;display:block;order:2!important;flex:0 0 24px!important;"
    f"background:#587dff;-webkit-mask:url('{_SEARCH_ICON_URI}') center/contain no-repeat;mask:url('{_SEARCH_ICON_URI}') center/contain no-repeat;"
    "filter:drop-shadow(0 1px 1px rgba(0,0,0,.55));}"
    ".st-key-analysebtn button:hover::before,.st-key-analysebtn button:focus-visible::before{background:#4c8dff;filter:drop-shadow(0 0 7px rgba(76,141,255,.42));}"
    ".st-key-analysebtn button:hover,.st-key-analysebtn button:focus-visible{"
    "background:rgba(76,111,255,.18)!important;border-color:#4c8dff!important;"
    "box-shadow:inset 0 0 0 1px #4c8dff,0 0 18px rgba(76,141,255,.24)!important;}"
    "@keyframes runCoinScan{0%{transform:translateX(-120%);}100%{transform:translateX(120%);}}"
    ".st-key-analysebtn button:hover,.st-key-analysebtn button:focus-visible,.st-key-analysebtn button:active{"
    "position:relative!important;overflow:hidden!important;}"
    ".st-key-analysebtn button:hover::after,.st-key-analysebtn button:focus-visible::after,.st-key-analysebtn button:active::after{"
    "content:'';position:absolute;top:0;bottom:0;left:0;width:100%;"
    "background:linear-gradient(90deg,transparent,rgba(139,92,246,.08),rgba(167,139,250,.34),rgba(139,92,246,.08),transparent);"
    "animation:runCoinScan .7s ease-out 1 forwards;pointer-events:none;}"
    ".st-key-analysebtn button:active{transform:translateY(1px) scale(.985)!important;"
    "background:rgba(76,111,255,.2)!important;"
    "border-color:#4c8dff!important;color:#f2f6ff!important;"
    "box-shadow:inset 0 0 0 1px rgba(76,141,255,.9),0 0 18px rgba(76,141,255,.28)!important;}"
    ".st-key-analysebtn button:active::before{background:#f2f6ff;filter:drop-shadow(0 0 5px rgba(76,141,255,.38));}"
    ".st-key-mobilefilterbtn{display:none!important;}"
    ".st-key-mobilefilterbtn button{width:48px!important;height:46px!important;min-height:46px!important;transform:none!important;"
    "border-radius:10px!important;background:rgba(18,28,40,.72)!important;"
    "border:1px solid rgba(76,141,255,.46)!important;padding:0!important;display:flex!important;"
    "align-items:center!important;justify-content:center!important;color:#e6e8eb!important;}"
    ".st-key-mobilefilterbtn button p{font-size:0!important;line-height:0!important;}"
    ".st-key-mobilefilterbtn button::before{content:'';width:24px;height:24px;display:block;"
    f"background-color:#f2f4f8;-webkit-mask:url('{_FILTER_ICON_URI}') center/contain no-repeat;mask:url('{_FILTER_ICON_URI}') center/contain no-repeat;"
    "filter:drop-shadow(0 1px 1px rgba(0,0,0,.65));}"
    ".st-key-mobilefilterbtn button:hover{border-color:#4c8dff!important;background:rgba(76,141,255,.14)!important;}"
    ".st-key-chartupload{width:100%!important;max-width:none!important;margin:0!important;padding:0!important;}"
    ".st-key-chartupload [data-testid='stFileUploaderDropzone']{height:40px!important;min-height:40px!important;}"
    ".v3capline{display:none!important;}"
    ".gradehelpbox,.costhelpbox{right:auto!important;left:0!important;width:min(340px,calc(100vw - 36px))!important;}"
    "}"
    "</style>",
    unsafe_allow_html=True,
)


def _normalise_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if symbol and not symbol.endswith("USDT"):
        symbol += "USDT"
    return symbol


def _save_uploaded_chart(uploaded_file, symbol: str, timeframe: str) -> tuple[str, dict]:
    os.makedirs(CHART_UPLOAD_DIR, exist_ok=True)
    original_name = uploaded_file.name or "chart.png"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    safe_timeframe = re.sub(r"[^A-Z0-9]", "", (timeframe or "4H").upper())
    filename = f"{symbol}_{safe_timeframe}_{int(time.time())}{ext}"
    image_path = os.path.join(CHART_UPLOAD_DIR, filename)
    with open(image_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return image_path, {
        "url": "Uploaded TradingView chart screenshot",
        "title": original_name,
        "observed_symbol": symbol,
        "timeframe": timeframe,
        "source": "Trade Setup screenshot upload",
    }


if "analysis_setup_chart" not in st.session_state:
    st.session_state.analysis_setup_chart = "4H"
if "analysis_prompt_mode" not in st.session_state:
    st.session_state.analysis_prompt_mode = "ai"


def _set_prompt_mode(mode: str) -> None:
    st.session_state.analysis_prompt_mode = "ai" if mode == "ai" else "prompt"


def _openai_api_key() -> str:
    key = (os.getenv("OPENAI_API_KEY") or os.getenv("openai_api_key") or "").strip()
    if key:
        return key

    try:
        key = (st.secrets.get("openai_api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass

    try:
        openai_cfg = st.secrets.get("openai") or {}
        return (openai_cfg.get("api_key") or "").strip()
    except Exception:
        return ""


def _render_run_coin_loading_style() -> None:
    st.markdown(
        """
        <style>
        .st-key-analysebtn button{
            position:relative!important;
            overflow:hidden!important;
            background:rgba(76,111,255,.2)!important;
            border-color:#4c8dff!important;
            box-shadow:inset 0 0 0 1px rgba(76,141,255,.9),0 0 18px rgba(76,141,255,.28)!important;
        }
        .st-key-analysebtn button::after{
            content:''!important;
            position:absolute!important;
            top:0!important;
            bottom:0!important;
            left:0!important;
            width:100%!important;
            background:linear-gradient(90deg,transparent,rgba(139,92,246,.08),rgba(167,139,250,.34),rgba(139,92,246,.08),transparent)!important;
            animation:runCoinScan .7s ease-out infinite!important;
            pointer-events:none!important;
            z-index:1!important;
        }
        .st-key-analysebtn button p,
        .st-key-analysebtn button::before{
            position:relative!important;
            z-index:2!important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

_brow = st.container(key="brandrow")
_brow.markdown(chrome.brand_html("TRADE", "SETUP"), unsafe_allow_html=True)
_brow.text_input(
    "Ticker",
    key="analysis_symbol_input",
    placeholder="TICKER",
    label_visibility="collapsed",
)
_brow.pills(
    "Setup chart",
    ["1D", "4H", "1H", "15M", "1M"],
    selection_mode="single",
    key="analysis_setup_chart",
    label_visibility="collapsed",
)
with _brow.container(key="chartupload"):
    st.file_uploader(
        "Upload Chart",
        type=["png", "jpg", "jpeg", "webp"],
        key="analysis_chart_upload",
        help="AI mode uses this chart image as the primary evidence.",
    )
_prompt_ai_on = st.session_state.get("analysis_prompt_mode") == "ai"
with _brow.container(key="promptseg"):
    st.button(
        "AI",
        key="segai_on" if _prompt_ai_on else "segai_off",
        on_click=_set_prompt_mode,
        args=("ai",),
    )
    st.button(
        "Prompt",
        key="segprompt_off" if _prompt_ai_on else "segprompt_on",
        on_click=_set_prompt_mode,
        args=("prompt",),
    )
_brow.button("Filter", key="mobilefilterbtn")

def _run_trade_setup_analysis(requested: str, setup_chart: str, prompt_mode: str) -> None:
    if not requested:
        return
    st.session_state.analysis_request_submitted = True
    st.session_state.openai_analysis_error = None
    try:
        api_key = _openai_api_key()
        if not api_key or api_key == "PASTE_OPENAI_API_KEY_HERE":
            raise RuntimeError("OpenAI API key is not configured for this app.")
        if prompt_mode == "ai":
            uploaded_chart = st.session_state.get("analysis_chart_upload")
            if not uploaded_chart:
                raise RuntimeError("Upload a TradingView chart screenshot to run AI mode.")
            chart_image_path, chart_meta = _save_uploaded_chart(uploaded_chart, requested, setup_chart)
            spinner_label = f"Analysing {requested} chart screenshot..."
            analysis_kwargs = {
                "prompt_mode": "ai",
                "chart_image_path": chart_image_path,
                "chart_image_meta": chart_meta,
            }
        else:
            spinner_label = f"Analysing {requested} with OpenAI..."
            analysis_kwargs = {"prompt_mode": "prompt"}
        with st.spinner(spinner_label):
            openai_analysis.generate_dashboard_analysis(
                requested,
                api_key=api_key,
                setup_timeframe=setup_chart,
                **analysis_kwargs,
            )
        st.session_state.analysis_requested_symbol = requested
        st.rerun()
    except Exception as exc:
        st.session_state.openai_analysis_error = str(exc)

if _brow.button("Run Coin", key="analysebtn"):
    requested = _normalise_symbol(st.session_state.get("analysis_symbol_input", ""))
    setup_chart = st.session_state.get("analysis_setup_chart") or "4H"
    prompt_mode = st.session_state.get("analysis_prompt_mode") or "prompt"
    uploaded_chart = st.session_state.get("analysis_chart_upload")
    if not requested:
        pass
    elif prompt_mode == "ai" and not uploaded_chart:
        pass
    else:
        _render_run_coin_loading_style()
        _run_trade_setup_analysis(requested, setup_chart, prompt_mode)

# Show the requested symbol when the user has used the Analyse control; otherwise
# show the most recently generated analysis (newest analyses/<SYMBOL>.json).
symbol = st.session_state.get("analysis_requested_symbol") or dashboard.latest_symbol()
data = dashboard.load_analysis(symbol)

if st.session_state.get("openai_analysis_error"):
    st.error(st.session_state.openai_analysis_error, icon="⚠️")

# Caption hugging the divider line, directly under the heading (no wasted space).
if data:
    _m = data.get("meta", {})
    _last_analysed = _m.get("analysis_time") or data.get("generated_at") or "unknown"
    _openai = _m.get("openai") or {}
    _cost = _openai.get("estimated_cost_usd")
    _cost_label = f"~${_cost:.4f}" if isinstance(_cost, (int, float)) else "—"
    _token_label = ""
    if _openai:
        _token_label = (
            f"<span class='costhelp' tabindex='0'>i"
            f"<span class='costhelpbox'>"
            f"<b>OpenAI scan receipt</b><br>"
            f"<b>Model:</b> {html.escape(str(_openai.get('model') or '—'))}<br>"
            f"<b>Input tokens:</b> {_openai.get('input_tokens', '—')}<br>"
            f"<b>Cached input:</b> {_openai.get('cached_input_tokens', '—')}<br>"
            f"<b>Output tokens:</b> {_openai.get('output_tokens', '—')}<br>"
            f"<b>Total tokens:</b> {_openai.get('total_tokens', '—')}<br>"
            f"<b>Estimated cost:</b> {_cost_label}<br>"
            f"<span>{html.escape(str(_openai.get('pricing_note') or 'Estimate only.'))}</span>"
            f"</span></span>"
        )
    _grade_key = (
        "<span class='gradehelp' tabindex='0'>i"
        "<span class='gradehelpbox'>"
        "<b>Trade grade key</b><br>"
        "<b>A</b>: validated setup, strong R:R, clean location, entry not stale, meaningful move remains.<br>"
        "<b>B</b>: good setup with weaker validation: mixed context, thinner confluence, incomplete trigger, confirmation dependency, or caveat.<br>"
        "<b>C</b>: watchlist / tactical only; plausible but early, late, aggressive, or needing too much to go right.<br>"
        "<b>D</b>: no valid trade setup: poor location, stale pattern, bad R:R, invalid structure, or hypothetical only.<br>"
        "<b>Cap:</b> stale, lagging, chasing, or mostly resolved setups cannot be A-grade."
        "</span></span>"
    )
    _cap = (
        f"<b>{data.get('symbol', symbol)}</b> · "
        f"<b>Last analysed:</b> {_last_analysed} · "
        f"<b>Chart setup:</b> {_m.get('setup_timeframe', '—')} · "
        f"<b>OpenAI:</b> {_cost_label}{_token_label} {_grade_key}"
    )
    st.markdown(
        "<style>.v3capline{color:#8b94a0;font-size:.8rem;line-height:1.3;margin:0 0 14px 0;"
        "padding-bottom:6px;border-bottom:1px solid #2a2f3a;}"
        ".gradehelp,.costhelp{position:relative;display:inline-flex;align-items:center;justify-content:center;"
        "width:16px;height:16px;margin-left:5px;border:1px solid #4c8dff;border-radius:50%;"
        "color:#9fc0ff;font-size:10px;font-weight:800;cursor:help;vertical-align:1px;}"
        ".gradehelpbox,.costhelpbox{display:none;position:absolute;right:0;top:22px;z-index:10;width:360px;"
        "padding:11px 12px;border:1px solid rgba(76,141,255,.45);border-radius:8px;"
        "background:#101722;color:#dce3ec;box-shadow:0 14px 32px rgba(0,0,0,.35);"
        "font-size:.74rem;line-height:1.45;font-weight:400;text-align:left;}"
        ".gradehelp:hover .gradehelpbox,.gradehelp:focus .gradehelpbox,"
        ".costhelp:hover .costhelpbox,.costhelp:focus .costhelpbox{display:block;}</style>"
        f"<div class='v3capline'>{_cap}</div>",
        unsafe_allow_html=True,
    )
    dashboard.render(data, symbol=symbol)
else:
    st.divider()
    if st.session_state.get("analysis_request_submitted"):
        st.info(
            f"Ready to run OpenAI analysis for **{symbol}**. Add the action prompt/API "
            "step next and this button can generate the dashboard result directly.",
            icon="✨",
        )
    else:
        st.warning(
            f"No analysis on file for **{symbol}**.",
            icon="📭",
        )
