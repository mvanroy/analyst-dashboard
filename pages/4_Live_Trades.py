from __future__ import annotations

import html
import json
import math
import os
import time
import base64
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import bybit
import chrome
import coinalyze
import icons

st.set_page_config(page_title="Live Trades", page_icon="⚡", layout="wide")
chrome.render_header("LIVE", "TRADES", "Bybit · USDT Perp · Auto-sync")
st_autorefresh(interval=90_000, key="live_trades_autorefresh")

_load_positions = st.cache_data(ttl=75, show_spinner=False)(bybit.fetch_open_positions)
_load_account = st.cache_data(ttl=90, show_spinner=False)(bybit.fetch_account_summary)
_load_closed_trades = st.cache_data(ttl=600, show_spinner=False)(bybit.fetch_closed_trades)


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTOR_MAP_PATH = os.path.join(ROOT_DIR, "live_trade_sectors.json")


@st.dialog("Close Position")
def _close_dialog(symbol: str):
    st.write(f"Confirm close request for **{symbol}**.")
    st.warning("Close execution is disabled because the configured Bybit key is read-only.")
    st.button("Confirm close position", disabled=True)
    if st.button("Cancel"):
        st.rerun()


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def _money(value, sign=False) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    prefix = "+" if sign and v >= 0 else ""
    return f"{prefix}${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


def _money_compact(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:.1f}K"
    return f"{sign}${v:,.0f}"


def _pct(value, sign=False, digits=2) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    prefix = "+" if sign and v >= 0 else ""
    return f"{prefix}{v:.{digits}f}%"


def _price(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 100:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _age_label(hours) -> str:
    if hours is None:
        return "—"
    seconds = max(0, int(float(hours) * 3600))
    if seconds < 60:
        return "<1m"
    minutes = seconds // 60
    days, rem = divmod(minutes, 1440)
    hrs, mins = divmod(rem, 60)
    if days:
        return f"{days}d {hrs}h"
    if hrs:
        return f"{hrs}h {mins}m" if mins else f"{hrs}h"
    return f"{mins}m"


def _r_label(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.2f}R"


def _cls(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "muted"
    if v > 0:
        return "green"
    if v < 0:
        return "red"
    return "muted"


def _liq_cls(row: dict) -> str:
    liq = row.get("liq")
    mark = row.get("mark")
    if not liq or not mark:
        return "muted"
    dist = abs(float(mark) - float(liq)) / float(mark) * 100 if mark else 999
    if dist <= 10:
        return "red"
    if dist <= 20:
        return "amber"
    return "muted"


def _initials(symbol: str) -> str:
    s = symbol.replace("USDT", "").replace("PERP", "")
    return s[:2].upper() if s else "?"


def _base_symbol(symbol: str) -> str:
    base = symbol or ""
    for quote in ("USDT", "USDC", "BUSD"):
        if base.endswith(quote):
            base = base[: -len(quote)]
            break
    return base


def _coin_icon(symbol: str, icon_lookup: dict[str, str]) -> str:
    asset = _initials(symbol)
    uri = icon_lookup.get(symbol, "")
    if uri:
        return f'<span class="rank-badge coin-symbol"><img src="{_esc(uri)}" alt="{_esc(asset)} logo" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'no-logo\');this.parentElement.textContent=\'{_esc(asset)}\';"></span>'
    return f'<span class="rank-badge coin-symbol no-logo">{_esc(asset)}</span>'


def _sector_icon(name: str) -> str:
    filename = {
        "DeFi": "sector-defi.svg",
        "NFT / Gaming": "sector-gaming.svg",
        "Memes": "sector-memes.svg",
        "Layer 1": "sector-layer-1.svg",
        "Layer 2": "sector-layer-2.svg",
        "Modular": "sector-modular.svg",
        "Oracle": "sector-oracle.svg",
        "RWA": "sector-rwa.svg",
        "AI": "sector-ai.svg",
        "Infrastructure": "sector-infrastructure.svg",
    }.get(name, "blank.svg")
    return chrome._inline_icon(filename)


def _svg_img(filename: str, alt: str = "") -> str:
    path = os.path.join(ROOT_DIR, "assets", filename)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
    except OSError:
        return ""
    return f'<img src="data:image/svg+xml;base64,{data}" alt="{_esc(alt)}">'


def _mini_coin(symbol: str, icon_lookup: dict[str, str]) -> str:
    return f"<span class='mini-coin'>{_coin_icon(symbol, icon_lookup)}<b>{_esc(symbol)}</b></span>"


def _spark(values, color="#8b5cf6") -> str:
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        vals = [0, vals[0] if vals else 0, 0]
    mn, mx = min(vals), max(vals)
    span = mx - mn or 1
    pts = []
    for i, v in enumerate(vals[-12:]):
        x = i / max(1, len(vals[-12:]) - 1) * 88
        y = 32 - ((v - mn) / span * 28 + 2)
        pts.append(f"{x:.1f},{y:.1f}")
    return f"<svg class='lt-spark' viewBox='0 0 88 34'><polyline points='{' '.join(pts)}' fill='none' stroke='{color}' stroke-width='2'/></svg>"


def _progress(width_pct, cls="green") -> str:
    w = max(0, min(100, float(width_pct or 0)))
    return f"<div class='lt-bar'><span class='{cls}' style='width:{w:.1f}%'></span></div>"


def _tone(value: str) -> str:
    return value if value in {"green", "amber", "red"} else "muted"


def _client_is_mobile() -> bool | None:
    try:
        headers = getattr(st.context, "headers", {}) or {}
        user_agent = str(headers.get("User-Agent") or headers.get("user-agent") or "").lower()
    except Exception:
        return None
    if not user_agent:
        return None
    mobile_markers = ("iphone", "android", "mobile", "ipod", "windows phone")
    return any(marker in user_agent for marker in mobile_markers)


def _returns(candles: list[dict], lookback: int = 24) -> pd.Series:
    closes = pd.Series([float(c["close"]) for c in candles if c.get("close")])
    if len(closes) < 3:
        return pd.Series(dtype=float)
    return closes.pct_change().dropna().tail(lookback)


def _return_pct(candles: list[dict], lookback: int = 24) -> float | None:
    closes = [float(c["close"]) for c in candles if c.get("close")]
    if len(closes) <= lookback:
        return None
    start = closes[-lookback - 1]
    end = closes[-1]
    return (end / start - 1) * 100 if start else None


@st.cache_data(ttl=600, show_spinner=False)
def _load_market_candles(symbols: tuple[str, ...]) -> dict[str, list[dict]]:
    out = {}
    for symbol in symbols:
        try:
            out[symbol] = bybit.fetch_market_klines(symbol, "60", 80)
        except Exception:
            out[symbol] = []
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_relative_strength_candles(symbols: tuple[str, ...]) -> dict[str, list[dict]]:
    out = {}
    for symbol in symbols:
        try:
            out[symbol] = bybit.fetch_market_klines(symbol, "15", 20)
        except Exception:
            out[symbol] = []
    return out


@st.cache_data(ttl=180, show_spinner=False)
def _load_market_ticker(symbol: str) -> dict:
    try:
        return bybit.fetch_market_ticker(symbol)
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def _load_btc_liquidation_map() -> dict:
    return coinalyze.liquidation_map("BTCUSDT", hours=24, interval="1hour")


@st.cache_data(ttl=600, show_spinner=False)
def _load_sector_map(_mtime: float = 0) -> dict[str, str]:
    try:
        with open(SECTOR_MAP_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _circuit_breaker(closed_trades: list[dict], equity: float) -> dict:
    today = datetime.now().date()
    todays = [t for t in closed_trades if (t.get("date") and t["date"].date() == today)]
    todays.sort(key=lambda t: t.get("closed_ts") or t.get("ts") or 0)
    day_pnl = sum(float(t.get("net") or 0) for t in todays)
    day_pct = day_pnl / equity * 100 if equity else 0
    streak = 0
    for trade in reversed(todays):
        if float(trade.get("net") or 0) < 0:
            streak += 1
        else:
            break
    blocked = streak >= 3 or day_pct <= -3
    if blocked:
        reason = "3 losing trades in a row" if streak >= 3 else f"daily loss {_pct(day_pct)}"
        score = max(0, min(100, 100 - streak * 22 + day_pct * 10))
        return {
            "tone": "red",
            "value": "Stop trading today",
            "detail": reason,
            "streak": streak,
            "day_pct": day_pct,
            "day_pnl": day_pnl,
            "score": score,
            "signals": 1,
        }
    score = max(0, min(100, 100 - streak * 12 + min(5, day_pct) * 2))
    signals = 4
    if streak:
        signals -= 1
    if day_pct < 0:
        signals -= 1
    return {
        "tone": "green",
        "value": "Keep trading",
        "detail": "No behavioral risk detected.",
        "streak": streak,
        "day_pct": day_pct,
        "day_pnl": day_pnl,
        "score": score,
        "signals": max(1, signals),
    }


def _btc_condition(btc_candles: list[dict]) -> dict:
    closes = pd.Series([float(c["close"]) for c in btc_candles if c.get("close")])
    vols = pd.Series([float(c["volume"]) for c in btc_candles if c.get("volume")])
    if len(closes) < 30:
        return {"tone": "amber", "value": "BTC data limited", "detail": "Waiting for enough candles", "ret_24": None, "vol_ratio": None}
    ema20 = closes.ewm(span=20).mean().iloc[-1]
    ema50 = closes.ewm(span=50).mean().iloc[-1]
    last = closes.iloc[-1]
    ret_24 = (last / closes.iloc[-25] - 1) * 100 if len(closes) >= 25 and closes.iloc[-25] else 0
    support = closes.tail(24).min()
    vol_ratio = vols.tail(6).mean() / vols.tail(48).mean() if len(vols) >= 48 and vols.tail(48).mean() else 1
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, pd.NA))))
    rsi_last = float(rsi.dropna().iloc[-1]) if len(rsi.dropna()) else None
    rsi_prev = float(rsi.dropna().iloc[-4]) if len(rsi.dropna()) >= 4 else rsi_last
    recent = closes.tail(12)
    prior = closes.tail(24).head(12)
    trend_down = recent.max() < prior.max() and recent.min() < prior.min()
    trend_up = recent.max() > prior.max() and recent.min() > prior.min()
    support_broken = last <= support * 1.003
    volume_strong = vol_ratio >= 1.25
    momentum_weak = rsi_last is not None and (rsi_last < 45 or (rsi_prev is not None and rsi_last < rsi_prev))
    if last < ema20 and (ret_24 <= -1.5 or last <= support * 1.003 or vol_ratio >= 1.8):
        tone = "red"
        value = "BTC structure broken"
        detail = f"{_pct(ret_24, True)} 24h - support pressure"
    elif last > ema20 > ema50 and ret_24 > 0 and vol_ratio < 1.6:
        tone = "green"
        value = "BTC supportive"
        detail = f"{_pct(ret_24, True)} 24h - trend intact"
    else:
        tone = "amber"
        value = "BTC mixed"
        detail = f"{_pct(ret_24, True)} 24h - choppy read"
    return {
        "tone": tone,
        "value": value,
        "detail": detail,
        "ret_24": ret_24,
        "vol_ratio": vol_ratio,
        "price": last,
        "support": support,
        "ema20": float(ema20),
        "ema50": float(ema50),
        "rsi": rsi_last,
        "trend_label": "Bullish" if trend_up else "Bearish" if trend_down else "Mixed",
        "trend_detail": "Higher highs / higher lows" if trend_up else "Lower highs / lower lows" if trend_down else "No clean sequence",
        "trend_ok": trend_up and last > ema20,
        "volume_label": "Strong" if volume_strong else "Weak" if vol_ratio < 0.85 else "Normal",
        "volume_detail": f"{vol_ratio:.2f}x recent average",
        "volume_ok": volume_strong and tone != "red",
        "support_label": "Broken" if support_broken else "Holding",
        "support_detail": f"{'Below' if support_broken else 'Above'} {_price(support)}",
        "support_ok": not support_broken,
        "momentum_label": "Weak" if momentum_weak else "Healthy",
        "momentum_detail": f"RSI {rsi_last:.1f}{' and falling' if rsi_prev is not None and rsi_last is not None and rsi_last < rsi_prev else ''}" if rsi_last is not None else "RSI unavailable",
        "momentum_ok": not momentum_weak,
        "spark": list(closes.tail(30)),
    }


def _portfolio_market_risk(
    positions: list[dict],
    candles: dict[str, list[dict]],
    relative_candles: dict[str, list[dict]],
    btc_ticker: dict,
    icon_lookup: dict[str, str],
) -> dict:
    btc = candles.get("BTCUSDT") or []
    btc_ret = _returns(btc)
    btc_move = _return_pct(btc)
    btc_move_15 = _return_pct(relative_candles.get("BTCUSDT") or [], 1)
    rows = []
    total_notional = sum(float(p.get("notional") or 0) for p in positions)
    high_corr_notional = 0.0
    for pos in positions:
        symbol = pos.get("coin")
        coin_rets = _returns(candles.get(symbol) or [])
        corr = None
        if len(coin_rets) >= 8 and len(btc_ret) >= 8:
            n = min(len(coin_rets), len(btc_ret), 50)
            corr = float(coin_rets.tail(n).corr(btc_ret.tail(n)))
        coin_move = _return_pct(candles.get(symbol) or [])
        coin_move_15 = _return_pct(relative_candles.get(symbol) or [], 1)
        rel = coin_move_15 - btc_move_15 if coin_move_15 is not None and btc_move_15 is not None else None
        if corr is not None and corr >= 0.70:
            high_corr_notional += float(pos.get("notional") or 0)
        rows.append(
            {
                "symbol": symbol,
                "corr": corr,
                "coin_move": coin_move,
                "coin_move_15": coin_move_15,
                "rel": rel,
                "notional": float(pos.get("notional") or 0),
            }
        )
    high_corr_pct = high_corr_notional / total_notional * 100 if total_notional else 0
    corr_tone = "red" if high_corr_pct > 65 else "amber" if high_corr_pct >= 40 else "green"
    strength = sorted([r for r in rows if r["rel"] is not None and r["rel"] >= 0], key=lambda r: r["rel"], reverse=True)
    weakness = sorted([r for r in rows if r["rel"] is not None and r["rel"] < 0], key=lambda r: r["rel"])
    rel_values = [r["rel"] for r in rows if r["rel"] is not None]
    corr_values = [r["corr"] for r in rows if r["corr"] is not None and not math.isnan(r["corr"])]
    avg_rel = sum(rel_values) / len(rel_values) if rel_values else None
    avg_corr = sum(corr_values) / len(corr_values) if corr_values else None
    outperform_pct = len([v for v in rel_values if v > 0]) / len(rel_values) * 100 if rel_values else None
    score = 50
    if avg_rel is not None:
        score += max(-25, min(25, avg_rel * 3))
    if outperform_pct is not None:
        score += (outperform_pct - 50) * 0.35
    if btc_move is not None and btc_move < 0 and high_corr_pct > 55:
        score -= 12
    score = max(0, min(100, score))
    strength_tone = "green" if score >= 70 else "amber" if score >= 45 else "red"
    if btc_move_15 is not None and btc_move_15 < -0.25 and avg_rel is not None and avg_rel > 0:
        strength_detail = "Leaders are holding up better than BTC."
    elif btc_move_15 is not None and btc_move_15 > 0.25 and avg_corr is not None and avg_corr >= 0.55:
        strength_detail = "BTC strength may support correlated positions."
    elif avg_rel is not None and avg_rel < 0:
        strength_detail = "Open alts are lagging BTC."
    else:
        strength_detail = "Relative strength is balanced across open trades."
    strong = strength
    weak = weakness
    btc_condition = _btc_condition(btc)
    if btc_ticker:
        btc_condition["price"] = btc_ticker.get("last_price") or btc_condition.get("price")
        btc_condition["ret_24"] = btc_ticker.get("price_24h_pct") if btc_ticker.get("price_24h_pct") is not None else btc_condition.get("ret_24")
        btc_condition["funding_rate"] = btc_ticker.get("funding_rate")
    return {
        "btc": btc_condition,
        "high_corr_pct": high_corr_pct,
        "high_corr_tone": corr_tone,
        "rows": rows,
        "strong": strong,
        "weak": weak,
        "btc_move": btc_move,
        "btc_move_15": btc_move_15,
        "avg_corr": avg_corr,
        "avg_rel": avg_rel,
        "outperform_pct": outperform_pct,
        "strength_score": score,
        "strength_tone": strength_tone,
        "strength_detail": strength_detail,
    }


def _sector_exposure(positions: list[dict], sector_map: dict[str, str], icon_lookup: dict[str, str]) -> dict:
    buckets: dict[str, dict] = {}
    total = sum(float(p.get("notional") or 0) for p in positions)
    unknown = 0
    for pos in positions:
        symbol = pos.get("coin") or ""
        sector = sector_map.get(symbol, "Other")
        if sector == "Other":
            unknown += 1
        bucket = buckets.setdefault(sector, {"name": sector, "notional": 0.0, "coins": []})
        bucket["notional"] += float(pos.get("notional") or 0)
        bucket["coins"].append(
            {
                "symbol": symbol,
                "base": _base_symbol(symbol),
                "notional": float(pos.get("notional") or 0),
                "icon": _coin_icon(symbol, icon_lookup),
            }
        )

    colors = ["#f6b44b", "#4c8dff", "#9b6dff", "#20d884", "#64748b", "#ff4d5e"]
    sectors = []
    for idx, item in enumerate(sorted(buckets.values(), key=lambda x: x["notional"], reverse=True)):
        pct = item["notional"] / total * 100 if total else 0
        sectors.append(
            {
                "name": item["name"],
                "notional": item["notional"],
                "pct": pct,
                "coins": sorted(item["coins"], key=lambda x: x["notional"], reverse=True),
                "color": colors[idx % len(colors)],
                "icon": _sector_icon(item["name"]),
            }
        )

    leader = sectors[0] if sectors else {"name": "No sector", "pct": 0}
    hhi = sum((float(s.get("pct") or 0) / 100) ** 2 for s in sectors)
    n = len(sectors)
    min_hhi = 1 / n if n else 0
    normalized_hhi = (hhi - min_hhi) / (1 - min_hhi) if n > 1 else (1 if n == 1 else 0)
    normalized_hhi = max(0, min(1, normalized_hhi))
    score = max(0, min(100, (1 - normalized_hhi) * 100))
    tone = "red" if normalized_hhi >= 0.55 else "amber" if normalized_hhi >= 0.25 else "green"
    headline = (
        "No open sector exposure"
        if not sectors
        else f"{leader['name']} concentration high"
        if normalized_hhi >= 0.55
        else f"{leader['name']} exposure elevated"
        if normalized_hhi >= 0.25
        else "Sector exposure balanced"
    )
    summary = (
        "No open positions are currently feeding the sector monitor."
        if not sectors
        else "Keep sizing balanced across sectors. Avoid adding anything that throws the balance off."
        if normalized_hhi < 0.25
        else f"Avoid adding more {leader['name']} exposure until current book is reduced."
    )
    risk_label = "High concentration risk" if tone == "red" else "Moderate concentration risk" if tone == "amber" else "Sector spread controlled"
    return {
        "tone": tone,
        "leader": leader["name"],
        "pct": float(leader.get("pct") or 0),
        "sectors": sectors,
        "totals": {s["name"]: s["notional"] for s in sectors},
        "detail": f"{leader['name']} {_pct(leader.get('pct') or 0)} largest exposure" if sectors else "No open exposure",
        "unknown": unknown,
        "score": score,
        "headline": headline,
        "summary": summary,
        "risk_label": risk_label,
        "hhi": hhi,
        "normalized_hhi": normalized_hhi,
    }


def _risk_cards_html(circuit: dict, market: dict, sector: dict, icon_lookup: dict[str, str], liquidation_map: dict | None = None) -> str:
    btc = market["btc"]
    total_sector = sum(sector["totals"].values())

    def status(tone: str) -> str:
        return {"green": "NORMAL", "amber": "WATCH", "red": "WARNING"}.get(tone, "WATCH")

    def ring(value, tone: str, label: str) -> str:
        val = max(0, min(100, float(value or 0)))
        return (
            f"<div class='advisor-ring {tone}' style='--p:{val:.1f}'>"
            f"<div><b>{val:.0f}</b><span>{label}</span></div></div>"
        )

    def evidence(label: str, value: str, cls: str = "") -> str:
        return f"<div class='advisor-evidence-row'><span>{_esc(label)}</span><b class='{cls}'>{value}</b></div>"

    rel_rows = [r for r in market.get("rows", []) if r.get("rel") is not None]
    rel_scale = max(1.0, min(10.0, math.ceil(max([abs(float(r.get("rel") or 0)) for r in rel_rows] or [1]))))

    def rel_bar(row: dict, tone: str) -> str:
        rel = float(row.get("rel") or 0)
        width = min(50, abs(rel) / rel_scale * 50)
        fill_cls = "pos" if rel >= 0 else "neg"
        symbol = row.get("symbol") or ""
        return (
            f"<div class='rs-row'>"
            f"{_coin_icon(symbol, icon_lookup)}"
            f"<b>{_esc(_base_symbol(symbol))}</b>"
            f"<strong class='{tone}'>{_pct(rel, True)}</strong>"
            f"<div class='rs-track'><i></i><span class='{fill_cls}' style='width:{width:.1f}%'></span></div>"
            f"</div>"
        )

    leaders = "".join(rel_bar(r, "green") for r in market["strong"]) or "<div class='advisor-empty'>No clear leaders yet</div>"
    laggards = "".join(rel_bar(r, "red") for r in market["weak"]) or "<div class='advisor-empty'>No clear laggards yet</div>"

    sector_items = sector.get("sectors", [])
    sector_rows = []
    for item in sector_items[:5]:
        pct = float(item.get("pct") or 0)
        coins = "".join(
            f"<span class='advisor-sector-coin'>{coin['icon']}<strong>{_esc(coin['base'])}</strong></span>"
            for coin in item.get("coins", [])
        )
        sector_rows.append(
            "<div class='advisor-sector-row'>"
            f"<span class='advisor-sector-icon'>{item.get('icon', '')}</span>"
            "<div class='advisor-sector-copy'>"
            f"<strong>{_esc(item.get('name'))}</strong>"
            f"<small>{len(item.get('coins', []))} position{'s' if len(item.get('coins', [])) != 1 else ''}</small>"
            "</div>"
            f"<b>{_pct(pct)}</b>"
            f"<div class='advisor-sector-bar'><span style='width:{pct:.1f}%'></span></div>"
            f"<div class='advisor-sector-coins'>{coins}</div>"
            "</div>"
        )
    sector_rows_html = "".join(sector_rows) or "<div class='advisor-empty'>No open exposure</div>"
    corr_pct = market.get("avg_corr")
    corr_abs = abs(corr_pct or 0) * 100 if corr_pct is not None else market.get("high_corr_pct", 0)
    btc_warning = btc["tone"] == "red" or market["high_corr_tone"] == "red"
    btc_tone = "red" if btc_warning else "amber" if btc["tone"] == "amber" or market["high_corr_tone"] == "amber" else "green"
    btc_long_action = (
        "Reduce new long exposure. Prefer tighter risk."
        if btc_tone == "red"
        else "Use smaller size until BTC structure clears."
        if btc_tone == "amber"
        else "BTC backdrop is supportive for longs."
    )
    btc_short_action = (
        "BTC weakness can support short ideas; avoid chasing stretched downside."
        if btc_tone == "red"
        else "Shorts need cleaner confirmation while BTC is mixed."
        if btc_tone == "amber"
        else "BTC strength works against shorts; require stronger invalidation."
    )
    btc_status = (
        "Breaking support"
        if btc_tone == "red"
        else "Choppy structure"
        if btc_tone == "amber"
        else "Trend intact"
    )
    btc_long_action_label = (
        "No new longs"
        if btc_tone == "red"
        else "Reduce size"
        if btc_tone == "amber"
        else "Longs allowed"
    )
    btc_short_action_label = (
        "Short bias supported"
        if btc_tone == "red"
        else "Wait for confirmation"
        if btc_tone == "amber"
        else "Careful with shorts"
    )
    btc_slider = 88 if btc_tone == "red" else 50 if btc_tone == "amber" else 14

    def btc_state_tone(value: str, ok: bool | None) -> str:
        normalized = (value or "").lower()
        if ok is None or normalized in {"unavailable", "unknown"}:
            return "muted"
        if normalized in {"bullish", "strong", "holding", "healthy", "normal"}:
            return "green"
        if normalized in {"mixed"}:
            return "amber"
        if normalized in {"bearish", "weak", "broken", "stretched"}:
            return "red"
        return "green" if ok else "red"

    def btc_check(label: str, detail: str, value: str, ok: bool | None) -> str:
        cls = btc_state_tone(value, ok)
        symbol = "•" if ok is None else "✓" if cls == "green" else "×" if cls == "red" else "–"
        return (
            f"<div class='btc-check'><i class='{cls}'>{symbol}</i>"
            f"<div><b>{_esc(label)}</b><small>{_esc(detail)}</small></div>"
            f"<strong class='{cls}'>{_esc(value)}</strong></div>"
        )

    funding_rate = btc.get("funding_rate")
    funding_ok = funding_rate is not None and abs(float(funding_rate)) < 0.03
    funding_label = "Unavailable" if funding_rate is None else "Normal" if funding_ok else "Stretched"
    funding_detail = "Bybit funding not returned" if funding_rate is None else f"{float(funding_rate):+.4f}%"
    correlated = sorted(
        [r for r in market.get("rows", []) if r.get("corr") is not None and not math.isnan(r.get("corr"))],
        key=lambda r: abs(float(r.get("corr") or 0)),
        reverse=True,
    )
    correlated_rows = "".join(
        f"<span>{_mini_coin(r.get('symbol') or '', icon_lookup)}<b>{float(r.get('corr') or 0):.2f}</b></span>"
        for r in correlated[:3]
    ) or "<em>No correlated live trades yet</em>"
    btc_checks = "".join(
        [
            btc_check("Trend Direction", btc.get("trend_detail") or "No clean sequence", btc.get("trend_label") or "Mixed", bool(btc.get("trend_ok"))),
            btc_check("Volume Trend", btc.get("volume_detail") or "Volume unavailable", btc.get("volume_label") or "Unknown", bool(btc.get("volume_ok"))),
            btc_check("Key Support", btc.get("support_detail") or "Support unavailable", btc.get("support_label") or "Unknown", bool(btc.get("support_ok"))),
            btc_check("Momentum (RSI)", btc.get("momentum_detail") or "Momentum unavailable", btc.get("momentum_label") or "Unknown", bool(btc.get("momentum_ok"))),
            btc_check("Funding Rate", funding_detail, funding_label, funding_ok if funding_rate is not None else None),
        ]
    )
    systems_ok = all(t != "red" for t in [btc_tone, market["strength_tone"], sector["tone"]])
    avg_rel = market.get("avg_rel")
    strength_word_cls = "green" if avg_rel is not None and avg_rel > 0.25 else "red" if avg_rel is not None and avg_rel < -0.25 else "amber"
    sector_headline = _esc(sector.get("headline"))
    sector_headline = sector_headline.replace(" balanced", " <span class='advisor-sector-good'>balanced</span>")
    sector_headline = sector_headline.replace(" high", " <span class='amber'>high</span>")
    sector_headline = sector_headline.replace(" elevated", " <span class='amber'>elevated</span>")
    sector_score_detail = (
        f"HHI {float(sector.get('hhi') or 0):.2f} · normalized {float(sector.get('normalized_hhi') or 0):.2f}"
    )
    sector_hhi_info = (
        "HHI measures concentration by squaring each sector exposure weight and adding them up. "
        "This card normalizes HHI against the number of live sectors, so an even one-position-per-sector book does not get flagged as concentrated. "
        "Lower HHI = more diversified. Higher HHI = more concentrated."
    )
    bias_toggle = (
        "<div class='btc-bias-toggle'>"
        "<input id='btc-bias-long' name='btc-bias-view' type='radio' checked>"
        "<label class='long' for='btc-bias-long'>Long</label>"
        "<input id='btc-bias-short' name='btc-bias-view' type='radio'>"
        "<label class='short' for='btc-bias-short'>Short</label>"
        "</div>"
    )
    liquidation_map = liquidation_map or {}
    liq_buckets = liquidation_map.get("buckets") or []
    max_liq_bucket = max([float(row.get("total") or 0) for row in liq_buckets] or [1])
    liq_bars = "".join(
        f"<i style='height:{max(4, min(100, (float(row.get('total') or 0) / max_liq_bucket * 100))):.1f}%'></i>"
        for row in liq_buckets
    ) or "".join(f"<i style='height:{height}%'></i>" for height in [46, 78, 70, 62, 48, 32, 44, 54, 38, 25, 22, 34, 49, 30, 45, 43, 40, 52, 63, 74, 82, 39, 47, 28])
    liq_total_label = _money_compact(liquidation_map.get("total_liquidations")) if liquidation_map.get("available") else "Feed unavailable"
    liq_longs_label = _money_compact(liquidation_map.get("long_liquidations")) if liquidation_map.get("available") else "—"
    liq_shorts_label = _money_compact(liquidation_map.get("short_liquidations")) if liquidation_map.get("available") else "—"
    liq_note = (
        f"{_esc(liquidation_map.get('source') or 'Coinalyze')} · {_esc(liquidation_map.get('future_exchange') or 'Futures')} · 1h buckets"
        if liquidation_map.get("available")
        else _esc(liquidation_map.get("error") or "Connect CoinGlass, Coinalyze, or Hyblock for live totals.")
    )
    return f"""
<div class='advisor-head'>
  <div><b>LIVE RISK MONITORS</b></div>
</div>
<div class='advisor-grid'>
  <div class='advisor-card btc-card {btc_tone}'>
    <div class='advisor-top btc-top'><span class='advisor-icon btc-icon'>{_svg_img('btc-correlation.svg', 'BTC')}</span><div><b>BTC CORRELATION FILTER</b><small>COR cut off</small></div>{bias_toggle}</div>
    <div class='btc-structure'>
      <div class='btc-structure-copy'>
        <span>BTC MARKET STRUCTURE</span>
        <h3 class='{btc_tone}'>{_esc(btc_status)}</h3>
      </div>
      <div class='btc-price-box'>
        <span>BTC PRICE (USDT)</span>
        <b>{_price(btc.get("price"))}</b>
        <strong class='{_cls(btc.get("ret_24"))}'>{_pct(btc.get("ret_24"), True)} 24h</strong>
        {_spark(btc.get("spark") or [], "#ff4d5e" if btc_tone == "red" else "#e0a33e" if btc_tone == "amber" else "#20d884")}
      </div>
      <p class='btc-summary btc-long-copy'>{_esc(btc.get("momentum_label") or "Momentum")} momentum · {_esc(btc.get("volume_label") or "Volume")} volume · {_esc(btc_long_action)}</p>
      <p class='btc-summary btc-short-copy'>{_esc(btc.get("momentum_label") or "Momentum")} momentum · {_esc(btc.get("volume_label") or "Volume")} volume · {_esc(btc_short_action)}</p>
    </div>
    <div class='btc-regime'>
      <div class='btc-regime-track'><i style='left:{btc_slider:.0f}%'></i></div>
      <div><b class='green'>↗ Trending</b><span>Aggressive longs allowed</span></div>
      <div><b class='amber'>⌁ Choppy</b><span>Reduce size or wait</span></div>
      <div><b class='red'>↘ Breaking</b><span>No new longs</span></div>
    </div>
    <div class='btc-lower'>
      <div class='btc-checklist'>
        <h4>STRUCTURE CHECKLIST</h4>
        {btc_checks}
      </div>
      <div class='liq-map'>
        <h4>24H LIQUIDATION MAP</h4>
        <span>Total Liquidations</span>
        <b>{liq_total_label}</b>
        <div class='liq-bars'>{liq_bars}</div>
        <div class='liq-split'><span>Longs:</span><b>{liq_longs_label}</b></div>
        <div class='liq-split'><span>Shorts:</span><b>{liq_shorts_label}</b></div>
        <small>{liq_note}</small>
      </div>
    </div>
  </div>
  <div class='advisor-card {_tone(market["strength_tone"])}'>
    <div class='advisor-top'><span class='advisor-icon advisor-plain-icon advisor-rs-main-icon'>{chrome._inline_icon('relative-strength-btc.svg')}</span><div><b>RELATIVE STRENGTH TO BTC</b><small>15m strength monitor</small></div><em>{status(market["strength_tone"])}</em></div>
    <div class='rs-summary'>
      <h3 class='{strength_word_cls}'>{_esc(market["strength_detail"])}</h3>
      <div class='rs-average'><span>Average vs BTC</span><b class='{_cls(avg_rel)}'>{_pct(avg_rel, True)}</b><small>15m</small></div>
    </div>
    <div class='rs-panel green-panel'>
      <div class='rs-panel-head'><div><b>RELATIVE STRENGTH</b><small>Outperforming BTC</small></div></div>
      <div class='rs-scale'><span>-{rel_scale:.0f}%</span><span>0%</span><span>+{rel_scale:.0f}%</span></div>
      {leaders}
    </div>
    <div class='rs-panel red-panel'>
      <div class='rs-panel-head'><div><b>RELATIVE WEAKNESS</b><small>Lagging behind BTC</small></div></div>
      <div class='rs-scale'><span>-{rel_scale:.0f}%</span><span>0%</span><span>+{rel_scale:.0f}%</span></div>
      {laggards}
    </div>
    <div class='rs-btc-exposure'>
      <h4>BTC-LINKED EXPOSURE</h4>
      <b class='{market["high_corr_tone"]}'>{_pct(market.get("high_corr_pct"))}</b>
      <small>High-correlation live notional</small>
      <div class='btc-correlated'>{correlated_rows}</div>
    </div>
  </div>
  <div class='advisor-card advisor-sector-card {_tone(sector["tone"])}'>
    <div class='advisor-top advisor-sector-top'><span class='advisor-icon advisor-plain-icon advisor-sector-main-icon'>{chrome._inline_icon('sector-exposure.svg')}</span><div><b>SECTOR EXPOSURE</b></div><em>{status(sector["tone"])}</em></div>
    <h3 class='advisor-sector-headline'>{sector_headline}</h3>
    <div class='advisor-sector-gauge-wrap'>
      <div class='advisor-sector-gauge'>
        <div class='advisor-sector-gauge-track'></div>
        <div class='advisor-sector-gauge-fill'></div>
        <div class='advisor-sector-gauge-pin'></div>
        <b>{float(sector.get("score") or 0):.0f}</b><small>/100</small>
      </div>
      <span>DIVERSIFICATION SCORE</span>
      <div class='advisor-sector-pill'><i></i>{_esc(sector.get("risk_label"))}<button class='advisor-sector-info' aria-label='HHI explanation'>i<span class='advisor-sector-tooltip'><strong>{_esc(sector_score_detail)}</strong>{_esc(sector_hhi_info)}</span></button></div>
    </div>
    <div class='advisor-sector-list'>{sector_rows_html}</div>
    <div class='advisor-foot'><span>{_pct(sector.get("pct"))} largest exposure</span></div>
  </div>
</div>
"""


def _tp_sl(row: dict) -> str:
    tp = row.get("tp")
    sl = row.get("sl")
    entry = row.get("entry")
    mark = row.get("mark")
    if not tp and not sl:
        return "<span class='muted'>Not set</span>"

    def line(label, price, cls):
        if not price or not entry or not mark:
            progress = 0
        else:
            total = abs(float(price) - float(entry)) or 1
            done = abs(float(mark) - float(entry)) / total * 100
            progress = max(0, min(100, done))
        return (
            f"<div class='targetline {cls}'><span>{label}</span>"
            f"<b>{_price(price)}</b>{_progress(progress, cls)}</div>"
        )

    parts = []
    if tp:
        parts.append(line("TP", tp, "green"))
    if sl:
        parts.append(line("SL", sl, "red"))
    return "".join(parts)


def _normalise(rows: list[dict], account: dict) -> list[dict]:
    equity = float(account.get("equity") or 0)
    out = []
    for idx, row in enumerate(rows):
        notional = float(row.get("notional") or 0)
        lev = float(row.get("leverage") or 0)
        margin = notional / lev if lev else 0.0
        upnl = float(row.get("upnl") or 0)
        risk = None
        if row.get("sl") and row.get("entry") and row.get("size"):
            risk = abs(float(row["entry"]) - float(row["sl"])) * float(row["size"])
        out.append(
            {
                **row,
                "id": f"{row.get('coin')}-{idx}",
                "margin_used": margin,
                "margin_pct_equity": margin / equity * 100 if equity else None,
                "initial_risk": risk,
                "r_multiple": upnl / risk if risk and risk > 0 else row.get("live_r"),
            }
        )
    return out


def _sort_rows(rows: list[dict], sort_key: str, descending: bool) -> list[dict]:
    key_map = {
        "Unrealized P&L": "upnl",
        "Size": "notional",
        "Entry": "entry",
        "Mark": "mark",
        "R Multiple": "r_multiple",
        "Margin": "margin_used",
        "Liquidation": "liq",
        "Duration": "age_h",
        "Leverage": "leverage",
    }
    field = key_map.get(sort_key, "upnl")
    return sorted(rows, key=lambda r: float(r.get(field) or 0), reverse=descending)


def _group_rows(rows: list[dict], group_by: str) -> list[tuple[str | None, list[dict]]]:
    if group_by == "None":
        return [(None, rows)]
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        if group_by == "Direction":
            key = row.get("direction") or "Unknown"
        elif group_by == "Coin":
            key = row.get("coin") or "Unknown"
        elif group_by == "Profit / Loss":
            key = "Profit" if float(row.get("upnl") or 0) >= 0 else "Loss"
        elif group_by == "Leverage":
            key = f"{float(row.get('leverage') or 0):g}x"
        elif group_by == "Duration":
            h = float(row.get("age_h") or 0)
            key = "<1h" if h < 1 else "1-4h" if h < 4 else "4-24h" if h < 24 else "1d+"
        else:
            key = "Other"
        buckets.setdefault(key, []).append(row)
    return list(buckets.items())


st.markdown(
    "<style>"
    + chrome._PAGE_BG_CSS.replace("<style>", "").replace("</style>", "")
    + """
.lt-wrap{max-width:1600px;margin:0 auto;}
[data-testid="stElementContainer"]:has(style){height:0!important;min-height:0!important;margin:0!important;padding:0!important;}
.lt-top{display:flex;align-items:center;justify-content:flex-end;gap:12px;margin:-4px 0 14px;}
.lt-status{display:inline-flex;align-items:center;gap:8px;color:#aab2bd;font-size:12px;font-weight:650;}
.lt-dot{width:9px;height:9px;border-radius:50%;background:#0ecb81;box-shadow:0 0 14px rgba(14,203,129,.55);}
.lt-actions{display:flex;gap:8px;justify-content:flex-end;align-items:center;}
.lt-pill{border:1px solid rgba(139,148,160,.18);border-radius:8px;background:rgba(15,23,42,.38);padding:9px 12px;color:#dfe3e8;font-size:12px;font-weight:700;}
.lt-metrics{max-width:1600px;margin:-44px auto 14px;background:linear-gradient(145deg,rgba(12,17,32,.98),rgba(9,13,26,.92));border:1px solid rgba(148,163,184,.16);border-radius:10px;box-shadow:0 16px 42px rgba(0,0,0,.22);overflow:hidden;}
.lt-metric-grid{display:grid;grid-template-columns:1.05fr .95fr 1fr 1fr 1fr;gap:0;border-bottom:1px solid rgba(148,163,184,.12);}
.lt-metric-grid.secondary{grid-template-columns:1fr 1fr 1.15fr 1.15fr 1fr;border-bottom:0;}
.lt-metric{min-height:112px;padding:18px 22px;border-right:1px solid rgba(148,163,184,.12);position:relative;}
.lt-metric:last-child{border-right:0;}
.mobile-btc-status{display:none;}
.lt-metric .coin-symbol{width:42px;height:42px;flex-basis:42px;}
.lt-metric-cap{display:block;color:#9aa3af;text-transform:uppercase;letter-spacing:.08em;font-size:11px;font-weight:900;margin-bottom:16px;}
.lt-metric-big{display:flex;align-items:center;gap:10px;color:#f4f7fb;font-size:30px;font-weight:880;line-height:1;font-variant-numeric:tabular-nums;}
.lt-metric-big small{font-size:17px;font-weight:850;border:1px solid currentColor;border-radius:999px;padding:4px 9px;background:rgba(14,203,129,.10);}
.lt-metric-sub{display:block;color:#9aa3af;font-size:14px;font-weight:700;margin-top:13px;}
.lt-metric-link{color:#9b6dff;font-size:14px;font-weight:850;margin-top:18px;}
.lt-metric-icon{position:absolute;right:22px;top:45px;color:#8b5cf6;font-size:27px;line-height:1;}
.lt-metric-icon svg{width:28px;height:28px;display:block;color:currentColor;}
.lt-metric-icon svg *{fill:currentColor!important;stroke:currentColor!important;}
.lt-metric-performer{display:flex;align-items:center;justify-content:space-between;gap:12px;}
.lt-metric-performer-main{display:flex;align-items:center;gap:12px;min-width:0;}
.lt-metric-performer strong{display:block;color:#f4f7fb;font-size:16px;font-weight:900;line-height:1.1;}
.lt-metric-performer span{display:block;margin-top:6px;font-size:16px;font-weight:860;font-variant-numeric:tabular-nums;}
.lt-btc-value{display:block;color:#f4f7fb;font-size:30px;font-weight:880;line-height:1;font-variant-numeric:tabular-nums;}
.lt-btc-read{display:block;color:#9aa3af;font-size:14px;font-weight:700;line-height:1.25;margin-top:12px;}
.lt-btc-value.green{color:#0ecb81!important}.lt-btc-value.amber{color:#e0a33e!important}.lt-btc-value.red{color:#f6465d!important}
.lt-card{background:rgba(8,12,25,.72);border:1px solid rgba(86,100,138,.36);border-radius:11px;padding:15px 16px;min-height:136px;box-shadow:none;}
.lt-cap{font-size:10px;font-weight:850;letter-spacing:.07em;text-transform:uppercase;color:#9aa3af;margin-bottom:12px;}
.lt-big{font-size:30px;font-weight:850;line-height:1.05;color:#f2f5f9;font-variant-numeric:tabular-nums;}
.lt-sub{margin-top:8px;color:#aab2bd;font-size:13px;font-weight:650;}
.advisor-head{max-width:1600px;display:flex;align-items:center;justify-content:space-between;margin:18px auto 12px;}
.advisor-head>div{display:flex;align-items:center;gap:10px}.advisor-head b{font-size:16px;font-weight:900;letter-spacing:.02em;color:#f4f7fb}.advisor-head span{border:1px solid rgba(151,93,255,.35);background:rgba(151,93,255,.10);border-radius:999px;padding:5px 10px;color:#b989ff;font-size:12px;font-weight:800}.advisor-head p{margin:0;color:#aab2bd;font-size:12px;font-weight:750}.advisor-head i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-left:8px;background:#0ecb81;box-shadow:0 0 13px rgba(14,203,129,.5)}.advisor-head i.amber{background:#e0a33e;box-shadow:0 0 13px rgba(224,163,62,.5)}
.live-trades-head{justify-content:center;margin-bottom:2px;}
.live-trades-head>div{justify-content:center;}
.advisor-grid{max-width:1600px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:0 auto 16px;}
.advisor-card{position:relative;min-height:410px;border-radius:13px;background:linear-gradient(145deg,rgba(10,15,30,.92),rgba(8,12,25,.74));border:1px solid rgba(86,100,138,.38);padding:18px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.20);display:flex;flex-direction:column;}
.advisor-card.green{border-color:rgba(14,203,129,.52);box-shadow:inset 0 0 38px rgba(14,203,129,.08),0 18px 40px rgba(0,0,0,.20)}.advisor-card.amber{border-color:rgba(224,163,62,.55);box-shadow:inset 0 0 38px rgba(224,163,62,.08),0 18px 40px rgba(0,0,0,.20)}.advisor-card.red{border-color:rgba(246,70,93,.58);box-shadow:inset 0 0 38px rgba(246,70,93,.09),0 18px 40px rgba(0,0,0,.20)}
.advisor-top{display:grid;grid-template-columns:50px minmax(0,1fr) auto;gap:13px;align-items:center;margin-bottom:18px}.advisor-icon{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(139,148,160,.12);border:1px solid currentColor;font-size:13px;font-weight:900;color:#8b94a0;box-shadow:0 0 22px rgba(139,148,160,.16)}.advisor-icon svg{width:28px;height:28px;display:block;color:currentColor}.advisor-icon svg *{fill:currentColor!important;stroke:currentColor!important}.advisor-card.green .advisor-icon{color:#0ecb81;background:rgba(14,203,129,.14)}.advisor-card.amber .advisor-icon{color:#e0a33e;background:rgba(224,163,62,.14)}.advisor-card.red .advisor-icon{color:#f6465d;background:rgba(246,70,93,.14)}.advisor-plain-icon{background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;color:#f4f7fb!important}.advisor-plain-icon svg{width:34px!important;height:34px!important}.advisor-top b{display:block;color:#f3f5fb;font-size:13px;font-weight:900;letter-spacing:.025em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.advisor-top small{display:block;color:#9aa3af;font-size:11px;font-weight:750;margin-top:4px}.advisor-top em{font-style:normal;border:1px solid currentColor;border-radius:999px;padding:8px 13px;font-size:10px;font-weight:900;letter-spacing:.06em}.advisor-card.green em{color:#0ecb81;background:rgba(14,203,129,.10)}.advisor-card.amber em{color:#e0a33e;background:rgba(224,163,62,.10)}.advisor-card.red em{color:#f6465d;background:rgba(246,70,93,.10)}
.advisor-main{display:grid;grid-template-columns:150px minmax(0,1fr);gap:18px;align-items:center;margin-bottom:18px}.advisor-main h3,.advisor-sector h3{margin:0 0 10px;color:#f4f7fb;font-size:25px;line-height:1.05;font-weight:900;text-transform:uppercase}.advisor-card.green h3{color:#0ecb81}.advisor-card.amber h3{color:#e0a33e}.advisor-card.red h3{color:#f6465d}.advisor-main p,.advisor-sector p,.advisor-note{margin:9px 0;color:#aab2bd;font-size:14px;font-weight:700;line-height:1.35}.advisor-ring{--c:#8b94a0;width:136px;height:136px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--c) calc(var(--p)*1%),rgba(139,148,160,.18) 0);position:relative}.advisor-ring::after{content:"";position:absolute;inset:14px;border-radius:50%;background:#0b1020}.advisor-ring.green{--c:#0ecb81}.advisor-ring.amber{--c:#e0a33e}.advisor-ring.red{--c:#f6465d}.advisor-ring>div{position:relative;z-index:1;text-align:center}.advisor-ring b{display:block;color:#f6f8fb;font-size:30px;font-weight:900}.advisor-ring span{display:block;color:#aab2bd;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
.advisor-stats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid rgba(148,163,184,.12);border-bottom:1px solid rgba(148,163,184,.12);margin:14px 0;padding:12px 0}.advisor-stats div{text-align:center;border-right:1px solid rgba(148,163,184,.10)}.advisor-stats div:last-child{border-right:0}.advisor-stats b{display:block;color:#f4f7fb;font-size:16px;font-weight:900;font-variant-numeric:tabular-nums}.advisor-stats span{display:block;color:#9aa3af;font-size:11px;font-weight:750;margin-top:5px}
.advisor-action{border-top:1px solid rgba(148,163,184,.12);padding-top:14px;margin-top:12px}.advisor-action b,.advisor-list>b,.advisor-evidence::before{display:block;color:currentColor;font-size:10px;font-weight:900;letter-spacing:.09em;text-transform:uppercase;margin-bottom:9px}.advisor-action p{margin:0;color:#c8d0db;font-size:13px;line-height:1.45;font-weight:700}.advisor-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;color:#8b94a0;font-size:12px;font-weight:800;margin-top:auto;padding-top:18px}.advisor-foot span{color:currentColor}.advisor-foot button{height:32px;border-radius:8px;border:1px solid currentColor;background:rgba(255,255,255,.03);color:currentColor;padding:0 13px;font-size:12px;font-weight:850}
.btc-card{grid-column:span 2;gap:14px}.btc-card.red{background:linear-gradient(145deg,rgba(18,14,27,.96),rgba(8,12,25,.78))}.btc-top{grid-template-columns:42px minmax(0,1fr) auto;gap:11px;margin-bottom:2px}.btc-top b{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.12}.btc-top em{display:none}.btc-icon{color:#f6465d!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important}.btc-icon img{width:38px!important;height:38px!important;display:block;filter:brightness(0) invert(1)}.btc-structure{border:1px solid rgba(148,163,184,.12);border-radius:12px;padding:16px;display:grid;grid-template-columns:minmax(0,1fr) 190px;gap:18px;background:rgba(15,23,42,.20)}.btc-structure-copy>span,.btc-price-box>span,.btc-checklist h4,.btc-side-panel h4,.btc-why b{display:block;color:#aab2bd;font-size:10px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}.btc-structure-copy h3{margin:18px 0 9px;font-size:28px;line-height:1.05;font-weight:950;text-transform:none}.btc-structure-copy p{margin:8px 0;color:#b8c0cc;font-size:14px;font-weight:720;line-height:1.35}.btc-summary{display:block!important;grid-column:1 / -1;width:100%;margin:-4px 0 0;color:#8b94a0;font-size:10px;font-weight:620;line-height:1.35}.btc-price-box b{display:block;color:#f4f7fb;font-size:25px;font-weight:900;margin-top:14px;font-variant-numeric:tabular-nums}.btc-price-box strong{display:block;font-size:13px;font-weight:900;margin-top:6px}.btc-price-box .lt-spark{float:none;width:170px;height:54px;margin:12px 0 0}.btc-regime{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;border:1px solid rgba(148,163,184,.12);border-radius:12px;padding:13px;background:rgba(8,12,25,.20)}.btc-regime-track{grid-column:1 / 4;position:relative;height:8px;border-radius:999px;background:linear-gradient(90deg,#20d884,#e0a33e,#f6465d);margin:0 0 14px}.btc-regime-track i{position:absolute;top:50%;width:17px;height:17px;border-radius:50%;background:#f4f7fb;border:3px solid #f6465d;transform:translate(-50%,-50%)}.btc-regime div:not(.btc-regime-track){border-right:1px solid rgba(148,163,184,.10);padding:0 14px}.btc-regime div:last-child{border-right:0}.btc-regime b{display:block;font-size:13px;font-weight:900;text-transform:uppercase}.btc-regime span{display:block;color:#aab2bd;font-size:11px;font-weight:730;margin-top:6px;line-height:1.25}.btc-lower{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:14px}.btc-checklist,.btc-side-panel,.btc-why,.liq-map{border:1px solid rgba(148,163,184,.12);border-radius:12px;background:rgba(15,23,42,.20);padding:14px}.btc-check{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:10px;align-items:center;border-top:1px solid rgba(148,163,184,.09);padding:10px 0}.btc-check:first-of-type{border-top:0}.btc-check i{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;border:1px solid currentColor;font-style:normal;font-size:12px;font-weight:900}.btc-check b{display:block;color:#f4f7fb;font-size:13px;font-weight:840}.btc-check small{display:block;color:#aab2bd;font-size:11px;font-weight:700;margin-top:3px}.btc-check strong{font-size:12px;font-weight:900;text-transform:uppercase;text-align:right}.btc-side-panel>b{display:block;font-size:28px;font-weight:950;margin-top:10px;font-variant-numeric:tabular-nums}.btc-side-panel>small{display:block;color:#aab2bd;font-size:11px;font-weight:720;line-height:1.3;margin-top:3px}.btc-correlated{display:grid;gap:7px;margin:13px 0 15px}.btc-correlated span{display:flex;align-items:center;justify-content:space-between;gap:7px;color:#c8d0db;font-size:12px}.btc-correlated .mini-coin .rank-badge{width:22px;height:22px;flex-basis:22px}.btc-correlated .mini-coin b{font-size:11px}.btc-correlated b{font-size:12px;font-weight:900;color:#f4f7fb}.btc-correlated em{color:#8b94a0;font-size:11px;font-style:normal}.liq-map{margin-top:14px}.liq-map>span{display:block;color:#c8d0db;font-size:13px;font-weight:720;margin-top:13px}.liq-map>b{display:block;color:#f6465d;font-size:22px;font-weight:950;line-height:1.05;margin-top:8px}.liq-bars{height:105px;display:flex;align-items:end;gap:3px;margin:18px 0 14px}.liq-bars i{flex:1;min-width:2px;border-radius:2px 2px 0 0;background:linear-gradient(180deg,rgba(255,77,94,.76),rgba(127,29,42,.54));box-shadow:0 0 8px rgba(246,70,93,.16)}.liq-split{display:grid;grid-template-columns:64px 1fr;gap:8px;align-items:center;color:#dfe3e8;font-size:14px;font-weight:760;margin-top:6px}.liq-split b{color:#f6465d;font-size:16px;font-weight:900}.liq-map small{display:block;color:#8b94a0;font-size:10px;font-weight:650;line-height:1.35;margin-top:11px}.btc-why{margin-top:auto}.btc-why p{margin:8px 0 0;color:#b8c0cc;font-size:13px;font-weight:720;line-height:1.35}
.advisor-strength{display:grid;grid-template-columns:minmax(0,1fr) 136px;gap:18px;align-items:center}.advisor-list{border:1px solid rgba(148,163,184,.12);border-radius:8px;background:rgba(15,23,42,.25);padding:12px}.advisor-list>b{color:#4c8dff}.advisor-list .lag{color:#9b6dff;margin-top:13px}.advisor-coin-row{display:flex;align-items:center;justify-content:space-between;gap:9px;color:#dfe3e8;font-size:13px;font-weight:750;margin:8px 0}.advisor-coin-row .mini-coin{min-width:0}.advisor-coin-row b{font-variant-numeric:tabular-nums}.advisor-empty{color:#8b94a0;font-size:12px;font-weight:700;margin:8px 0}
.rs-btc-exposure{border:1px solid rgba(148,163,184,.14);border-radius:10px;background:rgba(15,23,42,.20);padding:12px;margin-top:12px}
.rs-btc-exposure h4{margin:0;color:#f4f7fb;font-size:10px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
.rs-btc-exposure>b{display:block;font-size:25px;font-weight:950;margin-top:10px;font-variant-numeric:tabular-nums}
.rs-btc-exposure>small{display:block;color:#aab2bd;font-size:11px;font-weight:720;line-height:1.3;margin-top:3px}
.btc-lower>.liq-map{margin-top:0}
.liq-map h4{margin:0;color:#f4f7fb!important;font-size:10px!important;font-weight:900!important;letter-spacing:.07em!important;text-transform:uppercase!important}
.rs-summary{display:grid;gap:8px;margin-bottom:12px}.rs-summary h3{margin:0;color:#f4f7fb;font-size:19px;line-height:1.14;font-weight:900;text-transform:none}.rs-average{display:flex;align-items:baseline;gap:7px;color:#aab2bd;font-size:11px;font-weight:760;line-height:1}.rs-average span{color:#9aa3af;font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.rs-average b{font-size:15px;font-weight:900;font-variant-numeric:tabular-nums}.rs-average small{color:#8b94a0;font-size:10px;font-weight:760}.rs-panel{border:1px solid rgba(148,163,184,.14);border-radius:10px;background:rgba(15,23,42,.20);padding:11px;margin-top:10px}.rs-panel.green-panel{border-color:rgba(14,203,129,.30);background:rgba(14,203,129,.045)}.rs-panel.red-panel{border-color:rgba(246,70,93,.28);background:rgba(246,70,93,.04)}.rs-panel-head{display:block;margin-bottom:8px}.rs-panel-head b{display:block;color:currentColor;font-size:12px;font-weight:900;letter-spacing:.04em}.green-panel .rs-panel-head b{color:#0ecb81}.red-panel .rs-panel-head b{color:#f6465d}.rs-panel-head small{display:block;color:#aab2bd;font-size:10px;font-weight:720;margin-top:3px}.rs-scale{display:grid;grid-template-columns:1fr 1fr 1fr;margin:3px 0 4px;padding-left:142px;color:#8b94a0;font-size:10px;font-weight:800}.rs-scale span:nth-child(2){text-align:center}.rs-scale span:last-child{text-align:right}.rs-row{display:grid;grid-template-columns:28px 46px 56px minmax(74px,1fr);gap:8px;align-items:center;padding:6px 0}.rs-row .rank-badge{width:28px;height:28px;flex-basis:28px;font-size:7px}.rs-row>b{color:#f4f7fb;font-size:12px;font-weight:900;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rs-row>strong{font-size:12px;font-weight:900;font-variant-numeric:tabular-nums;text-align:right}.rs-track{height:24px;position:relative;background:linear-gradient(90deg,transparent 0,rgba(148,163,184,.15) 50%,transparent 100%);border-top:1px solid rgba(148,163,184,.10);border-bottom:1px solid rgba(148,163,184,.10)}.rs-track i{position:absolute;left:50%;top:-4px;bottom:-4px;width:1px;background:rgba(148,163,184,.48)}.rs-track span{position:absolute;top:4px;height:16px;border-radius:1px}.rs-track span.pos{left:50%;background:#20d884}.rs-track span.neg{right:50%;background:#ff4d5e}
.advisor-evidence{margin-top:14px;border:1px solid rgba(148,163,184,.12);border-radius:8px;background:rgba(15,23,42,.23);padding:12px}.advisor-evidence::before{content:"EVIDENCE";color:#4c8dff}.advisor-evidence-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;border-top:1px solid rgba(148,163,184,.10);padding:7px 0;color:#aab2bd;font-size:12px;font-weight:750}.advisor-evidence-row:first-of-type{border-top:0}.advisor-evidence-row b{font-size:13px;font-weight:900;font-variant-numeric:tabular-nums;color:#dfe3e8}
.advisor-sector{display:grid;grid-template-columns:minmax(0,1fr) 142px;gap:20px;align-items:center;margin:14px 0 16px}.advisor-sector span{display:block;color:#9aa3af;font-size:11px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.advisor-sector h3{font-size:37px;color:#e0a33e;margin-top:12px}.advisor-sector h3 small{font-size:21px;color:#b4bdca}.sector-donut{width:142px;height:142px;border-radius:50%;background:conic-gradient(var(--donut));display:grid;place-items:center;position:relative}.sector-donut::after{content:"";position:absolute;inset:35px;border-radius:50%;background:#0b1020}.sector-donut b,.sector-donut span{position:relative;z-index:1;text-align:center}.sector-donut b{display:block;color:#f4f7fb;font-size:26px;font-weight:900}.sector-donut span{font-size:11px;text-transform:none;letter-spacing:0;color:#aab2bd;margin-top:22px}.sector-risk-list{border:1px solid rgba(148,163,184,.12);border-radius:8px;background:rgba(15,23,42,.23);padding:11px 13px;display:grid;gap:9px}.sector-risk-row{display:flex;align-items:center;justify-content:space-between;gap:10px;color:#c8d0db;font-size:13px;font-weight:760}.sector-risk-row span{display:flex;align-items:center;gap:9px}.sector-risk-row i{width:10px;height:10px;border-radius:50%;display:inline-block}.sector-risk-row b{font-size:14px;color:#dfe3e8;font-weight:900;font-variant-numeric:tabular-nums}
.advisor-sector-card{background:linear-gradient(145deg,rgba(8,13,23,.99),rgba(7,13,25,.96));}
.advisor-sector-card::before{content:"";position:absolute;inset:0;background:radial-gradient(430px 210px at 36% 40%,rgba(244,247,251,.05),transparent 64%);pointer-events:none;}
.advisor-sector-card>*{position:relative;z-index:1}
.advisor-sector-main-icon{color:#f4f7fb!important;}
.advisor-sector-main-icon svg{width:34px;height:34px;color:currentColor;fill:currentColor;}
.advisor-rs-main-icon{color:#f4f7fb!important;}
.advisor-rs-main-icon svg{width:34px;height:34px;color:currentColor;fill:currentColor;}
.advisor-sector-top{align-items:center;margin-bottom:16px;}
.advisor-sector-headline{margin:0;color:#f4f7fb!important;font-size:20px!important;font-weight:850!important;line-height:1.13!important;text-transform:none!important;}
.advisor-sector-headline::first-letter{text-transform:uppercase}
.advisor-sector-good{color:#0ecb81;}
.advisor-sector-gauge-wrap{margin:16px auto 14px;display:grid;justify-items:center;gap:8px;max-width:230px;}
.advisor-sector-gauge{position:relative;width:200px;height:100px;overflow:hidden;}
.advisor-sector-gauge-track,.advisor-sector-gauge-fill{position:absolute;left:0;top:0;width:200px;height:200px;border-radius:50%;box-sizing:border-box;}
.advisor-sector-gauge-track{border:20px solid rgba(100,116,139,.20);clip-path:polygon(0 0,100% 0,100% 50%,0 50%);}
.advisor-sector-gauge-fill{border:20px solid transparent;border-left-color:#f6a21f;border-top-color:#a7ce54;border-right-color:#0ecb81;clip-path:polygon(0 0,100% 0,100% 50%,0 50%);filter:drop-shadow(0 0 10px rgba(14,203,129,.24));}
.advisor-sector-gauge::after{content:"";position:absolute;left:20px;right:20px;top:20px;height:160px;border-radius:50%;border:1px solid rgba(148,163,184,.13);}
.advisor-sector-gauge-pin{position:absolute;right:22px;top:28px;width:18px;height:18px;border-radius:50%;background:#101827;border:3px solid #0ecb81;box-shadow:0 0 10px rgba(14,203,129,.34);}
.advisor-sector-gauge b{position:absolute;left:0;right:0;top:43px;text-align:center;color:#f6a21f;font-size:32px;font-weight:900;line-height:1;font-variant-numeric:tabular-nums;}
.advisor-sector-gauge small{position:absolute;left:0;right:0;top:78px;text-align:center;color:#aab2bd;font-size:16px;font-weight:760;}
.advisor-sector-gauge-wrap>span{color:#b6c4d6;font-size:10px;font-weight:900;letter-spacing:.10em;}
.advisor-sector-pill{position:relative;display:inline-flex;align-items:center;gap:8px;max-width:100%;border:1px solid rgba(148,163,184,.18);border-radius:999px;background:rgba(15,23,42,.42);padding:7px 10px;color:#d7dce3;font-size:12px;font-weight:780;}
.advisor-sector-pill>i{width:8px;height:8px;border-radius:50%;background:#f4f7fb;box-shadow:none;}
.advisor-sector-pill button{width:18px;height:18px;border-radius:50%;border:1px solid rgba(148,163,184,.28);background:rgba(8,12,25,.50);color:#aab2bd;font-size:11px;font-weight:900;font-style:italic;line-height:1;padding:0;}
.advisor-sector-info{cursor:default;}
.advisor-sector-tooltip{display:none;position:absolute;right:0;bottom:calc(100% + 8px);width:210px;max-width:min(210px,calc(100vw - 48px));transform:none;text-align:left;border:1px solid rgba(148,163,184,.22);background:#101827;border-radius:8px;padding:10px 11px;color:#aab2bd;font-size:10px;font-weight:620;font-style:normal;line-height:1.4;box-shadow:0 18px 42px rgba(0,0,0,.42);z-index:8;}
.advisor-sector-tooltip strong{display:block;color:#d7dce3;font-size:11px;font-weight:850;margin-bottom:6px;}
.advisor-sector-info:hover .advisor-sector-tooltip{display:block;}
.advisor-sector-list{display:grid;gap:13px;margin:0;}
.advisor-sector-row{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:11px;align-items:center;}
.advisor-sector-icon{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;color:#f4f7fb;}
.advisor-sector-icon svg{width:34px;height:34px;display:block;color:currentColor;fill:currentColor;}
.advisor-sector-copy strong{display:block;color:#f4f7fb;font-size:13px;font-weight:850;line-height:1.1;}
.advisor-sector-copy small{display:block;color:#aab2bd;font-size:10px;font-weight:700;margin-top:5px;}
.advisor-sector-row>b{font-size:13px;font-weight:900;font-variant-numeric:tabular-nums;color:#f4f7fb;}
.advisor-sector-bar{grid-column:2 / 4;height:5px;border-radius:999px;background:rgba(148,163,184,.10);overflow:hidden;margin-right:48px;}
.advisor-sector-bar span{display:block;height:100%;border-radius:999px;background:#f4f7fb;}
.advisor-sector-coins{grid-column:2 / 4;display:flex;gap:5px;flex-wrap:wrap;}
.advisor-sector-coin{display:inline-flex;align-items:center;gap:4px;border:1px solid rgba(148,163,184,.12);background:rgba(8,12,25,.34);border-radius:999px;padding:2px 6px 2px 2px;color:#cbd3df;font-size:10px;font-weight:780;}
.advisor-sector-coin .rank-badge{width:16px;height:16px;flex-basis:16px;font-size:7px;}
.advisor-sector-coin strong{font-size:10px;font-weight:780;color:#d7dce3;}
.mini-coin{display:inline-flex;align-items:center;gap:5px;color:#dfe3e8;}
.mini-coin .rank-badge{width:20px;height:20px;flex-basis:20px;font-size:.42rem;}
.mini-coin b{font-size:12px;font-weight:700;}
.sector-list{margin-top:10px;display:grid;gap:5px;}
.risk-row{display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(148,163,184,.10);padding-top:5px;color:#aab2bd;font-size:13px;}
.risk-row b{color:#dfe3e8;font-weight:700;}
.green{color:#0ecb81!important}.red{color:#f6465d!important}.amber{color:#e0a33e!important}.purple{color:#9b6dff!important}.muted{color:#8b94a0!important}
.lt-trend-icon{width:42px;height:42px;display:inline-flex;align-items:center;justify-content:center;flex:0 0 42px;}
.lt-trend-icon svg{width:32px;height:32px;display:block;color:currentColor;}
.lt-trend-icon svg *{fill:currentColor!important;stroke:currentColor!important;}
.lt-spark{width:92px;height:36px;float:right;margin-top:-10px;opacity:.95;}
.lt-bar{height:5px;border-radius:999px;background:rgba(139,148,160,.16);overflow:hidden;margin-top:9px;}
.lt-bar span{display:block;height:100%;border-radius:999px}.lt-bar span.green{background:#0ecb81}.lt-bar span.amber{background:#e0a33e}.lt-bar span.red{background:#f6465d}.lt-bar span.purple{background:#8b5cf6}
.lt-panel{max-width:1600px;background:transparent;border:0;border-radius:0;box-shadow:none;overflow:visible;margin:0 auto;}
.lt-tabs{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(148,163,184,.14);padding:0 10px;min-height:55px;}
.lt-tabset{display:flex;gap:20px;align-items:center;}
.lt-tab{position:relative;display:inline-flex;text-decoration:none!important;padding:14px 0 12px;color:#aab2bd;font-size:.88rem;font-weight:400;line-height:1.1;}
.lt-tab:visited,.lt-tab:hover,.lt-tab:focus,.lt-tab:active{text-decoration:none!important;}
.lt-tab.active{color:#f4f7fb;}
.lt-tab.active::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#9b6dff;border-radius:999px;}
.lt-tab.long{color:#20D884}.lt-tab.short{color:#FF4D5E}.lt-tab:not(.active):hover{color:#dfe3e8;}
.lt-tools{display:none;}
.st-key-live_tab_selector{max-width:1600px;margin:0 auto -1px!important;background:transparent!important;border:0!important;border-radius:0!important;padding:0 10px!important;min-height:55px;display:flex;align-items:center;}
.st-key-live_tab_selector [data-testid="stElementContainer"]{border:0!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"]{width:auto!important;background:transparent!important;border:0!important;box-shadow:none!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] div[role="radiogroup"]{gap:20px!important;background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label{position:relative;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;color:#f4f7fb!important;padding:15px 0 13px!important;font-size:.88rem!important;font-weight:400!important;line-height:1.1!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input:checked){color:#f4f7fb!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input:checked)::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:currentColor;border-radius:999px;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:nth-child(2):has(input:checked){color:#20D884!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:nth-child(3):has(input:checked){color:#FF4D5E!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input[value="Long"]:checked),
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input[aria-label*="Long"]:checked){color:#20D884!important;}
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input[value="Short"]:checked),
.st-key-live_tab_selector [data-testid="stSegmentedControl"] label:has(input[aria-label*="Short"]:checked){color:#FF4D5E!important;}
.st-key-live_controls{max-width:1600px;margin:10px auto 16px!important;padding:0!important;}
.st-key-live_controls [data-testid="stHorizontalBlock"]{align-items:center!important;justify-content:flex-end!important;gap:8px!important;}
.st-key-live_controls [data-testid="stColumn"]{display:flex!important;align-items:center!important;min-width:0!important;max-width:190px!important;}
.st-key-live_controls [data-testid="stSelectbox"]{width:100%!important;}
.st-key-live_controls [data-baseweb="select"] > div{height:40px!important;min-height:40px!important;border:1px solid rgba(76,141,255,.38)!important;border-radius:10px!important;background:#0c1020!important;color:#dce3ec!important;box-shadow:none!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;display:flex!important;align-items:center!important;}
.st-key-live_controls [data-baseweb="select"] > div:hover{border-color:rgba(76,141,255,.58)!important;background:#0d1322!important;}
.st-key-live_controls [data-baseweb="select"] > div:focus-within{border-color:#4c8dff!important;box-shadow:0 0 0 1px rgba(76,141,255,.14)!important;}
.st-key-live_controls [data-baseweb="select"] > div > div{height:100%!important;display:flex!important;align-items:center!important;padding-top:7px!important;padding-bottom:0!important;}
.st-key-live_controls [data-baseweb="select"] [data-testid="stMarkdownContainer"],.st-key-live_controls [data-baseweb="select"] p,.st-key-live_controls [data-baseweb="select"] span{margin:0!important;line-height:40px!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-size:.88rem!important;font-weight:400!important;letter-spacing:0!important;color:#8b94a0!important;}
.st-key-live_controls [data-baseweb="select"] svg{color:#9aa3af!important;width:18px!important;height:18px!important;}
.st-key-live_controls [data-testid="stToggle"]{height:40px!important;display:flex!important;align-items:center!important;}
.st-key-live_controls [data-testid="stToggle"] label{height:40px!important;border:1px solid rgba(76,141,255,.38)!important;border-radius:999px!important;background:#0c1020!important;padding:0 13px!important;display:flex!important;align-items:center!important;gap:8px!important;color:#dce3ec!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-size:.88rem!important;font-weight:400!important;line-height:1!important;box-shadow:none!important;}
.st-key-live_controls [data-testid="stToggle"] label p,.st-key-live_controls [data-testid="stToggle"] [data-testid="stMarkdownContainer"]{margin:0!important;line-height:1!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-weight:400!important;}
.st-key-live_controls [data-testid="stToggle"] label:hover{border-color:rgba(76,141,255,.58)!important;background:rgba(76,141,255,.08)!important;}
.st-key-live_controls [data-testid="stPopover"] button{height:40px!important;min-height:40px!important;border:1px solid rgba(76,141,255,.75)!important;border-radius:999px!important;background:rgba(76,141,255,.12)!important;color:#e6e8eb!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-size:.88rem!important;font-weight:400!important;line-height:1!important;padding:0 18px!important;box-shadow:none!important;display:flex!important;align-items:center!important;justify-content:center!important;}
.st-key-live_controls [data-testid="stPopover"] button p,.st-key-live_controls [data-testid="stPopover"] button [data-testid="stMarkdownContainer"]{margin:0!important;line-height:1!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-weight:400!important;}
.st-key-live_controls [data-testid="stPopover"] button:hover,.st-key-live_controls [data-testid="stPopover"] button:focus-visible{border-color:#4c8dff!important;color:#4c8dff!important;background:transparent!important;}
.btc-bias-toggle{justify-self:end;display:inline-flex;align-items:center;border:1px solid rgba(76,141,255,.38);border-radius:999px;background:#0c1020;overflow:hidden;}
.btc-bias-toggle input{position:absolute;opacity:0;pointer-events:none;}
.btc-bias-toggle label{height:38px;min-width:72px;padding:0 15px;display:inline-flex;align-items:center;justify-content:center;color:#8b94a0!important;text-decoration:none!important;font-size:.86rem;font-weight:400;line-height:1;border-radius:999px;cursor:pointer;}
.btc-bias-toggle input:checked + label{background:rgba(76,141,255,.16);box-shadow:inset 0 0 0 1px rgba(76,141,255,.76);}
.btc-bias-toggle #btc-bias-long:checked + label{color:#20D884!important;}
.btc-bias-toggle #btc-bias-short:checked + label{color:#FF4D5E!important;}
.btc-short-copy{display:none!important;}
.btc-card:has(#btc-bias-short:checked) .btc-long-copy{display:none!important;}
.btc-card:has(#btc-bias-short:checked) .btc-short-copy{display:block!important;}
.lt-table{width:100%;border-collapse:collapse;font-size:14px;}
.lt-table th{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#9aa3af;font-weight:850;padding:13px 12px;border-bottom:1px solid rgba(148,163,184,.14);background:rgba(15,23,42,.28);text-align:left;}
.lt-table td{padding:13px 12px;border-bottom:1px solid rgba(148,163,184,.10);color:#dfe3e8;font-variant-numeric:tabular-nums;vertical-align:middle;}
.lt-table td.r{font-size:15px;font-weight:650;}
.lt-table tr:last-child td{border-bottom:none}.r{text-align:right!important}.center{text-align:center!important;}
.coin{display:flex;align-items:center;gap:12px;min-width:126px}.rank-badge{width:34px;height:34px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;padding:0;border:1px solid rgba(160,168,184,.36);background:#252a3c;color:#f3f5fb;font-size:.52rem;letter-spacing:.02em;font-weight:900;font-variant-numeric:tabular-nums;position:relative;white-space:nowrap;overflow:hidden;flex:0 0 34px}.rank-badge.coin-symbol{background:rgba(21,25,39,.94);border-color:rgba(151,93,255,.42);box-shadow:0 0 12px rgba(151,93,255,.18)}.rank-badge img{width:100%;height:100%;object-fit:cover;display:block}.rank-badge.no-logo{background:linear-gradient(135deg,rgba(151,93,255,.16),rgba(21,25,39,.94));padding:0 3px;box-sizing:border-box}.sym{font-weight:850;color:#f4f7fb;font-size:14px}.lev{display:block;color:#8b94a0;font-size:12px;margin-top:2px}
.badge{display:inline-flex;align-items:center;justify-content:center;border-radius:5px;padding:3px 10px;font-size:12px;font-weight:850}.badge.long{background:rgba(32,216,132,.12);color:#20D884;border:1px solid rgba(32,216,132,.25)}.badge.short{background:rgba(255,77,94,.12);color:#FF4D5E;border:1px solid rgba(255,77,94,.25)}
.sizebar{width:112px;margin-top:8px}.tpcell{min-width:190px}.targetline{display:grid;grid-template-columns:34px 82px minmax(88px,1fr);gap:9px;align-items:center;font-size:13px;font-weight:850;margin:6px 0}.targetline span{letter-spacing:.03em}.targetline b{font-size:13px;font-weight:760;color:#dfe3e8;text-align:right}.targetline .lt-bar{margin:0;height:6px;background:rgba(139,148,160,.18)}
.empty{min-height:168px;padding:18px 12px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#8b94a0;gap:5px}.empty-whale{width:auto;height:auto;display:flex;align-items:center;justify-content:center;color:#fff;line-height:0;margin-bottom:2px}.empty-whale svg{width:160px!important;height:160px!important;display:block;color:currentColor;fill:currentColor}.empty-whale svg *{fill:currentColor!important;stroke:none!important;stroke-width:1px!important}.empty b{color:#f4f7fb;font-size:18px;margin:0}.empty>span:not(.empty-whale){font-size:12px;line-height:1.35}
.mobile-cards{display:none}.mtrade{background:linear-gradient(145deg,rgba(12,17,32,.98),rgba(9,13,26,.92));border:1px solid rgba(148,163,184,.16);border-radius:8px;padding:0;margin-bottom:10px;box-shadow:0 16px 42px rgba(0,0,0,.22);overflow:hidden}.mtrade summary{list-style:none}.mtrade summary::-webkit-details-marker{display:none}.mhead{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:14px;cursor:pointer}.mtrade-side{display:inline-flex;align-items:center;gap:8px;flex:0 0 auto}.mchev{color:#aab2bd;font-size:15px;line-height:1;transition:transform .16s ease}.mtrade[open] .mchev{transform:rotate(180deg)}.mtrade-body{padding:0 14px 14px;border-top:1px solid rgba(148,163,184,.10)}.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.mfield span{display:block;color:#8b94a0;text-transform:uppercase;letter-spacing:.06em;font-size:9px;font-weight:850}.mfield b{display:block;color:#f4f7fb;font-size:15px;margin-top:4px;font-variant-numeric:tabular-nums}
@media(max-width:1250px){.lt-metric-grid,.lt-metric-grid.secondary{grid-template-columns:repeat(2,1fr)}.lt-metric:nth-child(2n){border-right:0}.desktop-btc-status{display:none}.mobile-btc-status{display:block}}
@media(max-width:1250px){.advisor-grid{grid-template-columns:repeat(2,1fr)}.btc-card{grid-column:1 / -1}}
@media(max-width:760px){.st-key-brandrow{display:none!important}.lt-metrics{margin:-62px 0 12px}.lt-metric-grid,.lt-metric-grid.secondary{grid-template-columns:repeat(2,minmax(0,1fr));border-bottom:0}.lt-metric{min-height:88px;padding:14px 13px;border-right:1px solid rgba(148,163,184,.12);border-bottom:1px solid rgba(148,163,184,.12)}.lt-metric:nth-child(2n){border-right:0}.lt-metric-grid.secondary .lt-metric:nth-last-child(-n+2){border-bottom:0}.lt-metric-cap{font-size:9px;margin-bottom:10px;letter-spacing:.06em}.lt-metric-big{font-size:22px;gap:6px}.lt-metric-big small{font-size:11px;padding:3px 6px}.lt-metric-sub{font-size:11px;margin-top:8px}.lt-btc-value{font-size:22px}.lt-btc-read{font-size:11px;margin-top:8px}.lt-metric-link{font-size:11px;margin-top:10px}.lt-metric-icon{right:12px;top:36px;font-size:20px}.lt-metric .coin-symbol{width:30px;height:30px;flex-basis:30px}.lt-metric-performer{gap:8px}.lt-metric-performer-main{gap:8px}.lt-metric-performer strong{font-size:12px}.lt-metric-performer span{font-size:11px;margin-top:4px}.lt-trend-icon{width:30px;height:30px;flex:0 0 30px}.lt-trend-icon svg{width:24px;height:24px}.advisor-grid{grid-template-columns:1fr}.advisor-head{display:block}.advisor-head span{display:inline-flex;margin-top:8px}.advisor-head p{margin-top:8px}.advisor-main,.advisor-strength,.advisor-sector{grid-template-columns:1fr}.advisor-ring,.sector-donut{margin:0 auto}.advisor-card{min-height:0}.btc-card{grid-column:auto}.btc-top{grid-template-columns:38px minmax(0,1fr) auto!important;gap:9px;margin-bottom:12px}.btc-top b{font-size:12px!important;line-height:1.12!important}.btc-top small{font-size:10px!important}.btc-top em{padding:6px 9px!important;font-size:9px!important}.btc-icon img{width:32px!important;height:32px!important}.btc-structure{grid-template-columns:minmax(0,1fr) auto;align-items:start;padding:14px;gap:12px}.btc-structure-copy h3{font-size:19px!important;line-height:1.14!important;text-transform:none!important;margin:10px 0 7px!important;font-weight:900!important}.btc-structure-copy p{font-size:12px!important;line-height:1.35!important;margin:6px 0!important}.btc-pulse{color:#aab2bd!important;font-weight:760!important}.btc-structure-copy strong{font-size:12px!important;padding:7px 13px!important}.btc-price-box{margin-top:0;text-align:right;min-width:116px}.btc-price-box>span{font-size:9px!important;letter-spacing:.06em!important}.btc-price-box b{font-size:18px!important;margin-top:9px!important}.btc-price-box strong{font-size:11px!important}.btc-price-box .lt-spark{display:none!important}.btc-regime{padding:11px}.btc-regime div:not(.btc-regime-track){padding:0 6px}.btc-regime b{font-size:11px}.btc-regime span{font-size:9px}.btc-lower{grid-template-columns:1fr}.btc-check{grid-template-columns:24px minmax(0,1fr) auto;align-items:center}.btc-check strong{grid-column:auto;text-align:right;margin-top:0;align-self:center}.btc-side-panel{order:2}.btc-why{order:3}.lt-top{display:block}.lt-actions{justify-content:flex-start;margin-top:10px;overflow:auto}.st-key-live_controls{display:none!important}.st-key-live_tab_selector{min-height:42px!important;margin:0 auto -34px!important;padding:0 10px!important}.st-key-live_tab_selector [data-testid="stSegmentedControl"] label{padding:10px 0 8px!important}.lt-tabs{display:block;padding:0 10px 10px}.lt-tabset{overflow:auto}.lt-tools{margin-top:10px;overflow:auto}.desktop-table{display:none}.mobile-cards{display:block;padding:0 10px 10px;margin-top:-18px}.mtrade:first-child{margin-top:0}.mgrid{grid-template-columns:1fr 1fr}}
@media(max-width:760px){
  .btc-bias-toggle label{height:34px;min-width:58px;padding:0 11px;font-size:.76rem;}
  .btc-structure-copy{align-self:start!important;}
  .btc-price-box{align-self:start!important;padding-top:18px!important;}
  .btc-structure-copy h3{margin-top:9px!important;}
  .btc-price-box b{margin-top:0!important;line-height:1.14!important;}
  .btc-price-box strong{margin-top:4px!important;}
  .btc-summary{grid-column:1 / -1;width:100%;margin:-2px 0 0;color:#8b94a0;font-size:10px!important;font-weight:620;line-height:1.35;}
  .btc-card .btc-summary.btc-short-copy{display:none!important;}
  .btc-card .btc-summary.btc-long-copy{display:block!important;}
  .btc-card:has(#btc-bias-short:checked) .btc-summary.btc-long-copy{display:none!important;}
  .btc-card:has(#btc-bias-short:checked) .btc-summary.btc-short-copy{display:block!important;}
  .liq-map{margin-top:12px;padding:13px!important;}
  .liq-map>b{font-size:19px!important;}
  .liq-bars{height:82px;gap:2px;margin:14px 0 12px;}
  .liq-split{grid-template-columns:58px 1fr;font-size:13px;}
}
</style>""",
    unsafe_allow_html=True,
)

if not bybit.have_creds():
    st.warning("No Bybit API key configured — add `bybit_api_key` / `bybit_api_secret` to `journal_config.json`.")
    st.stop()

try:
    raw_positions = _load_positions()
except Exception as exc:
    st.error(f"Couldn't reach Bybit open positions: {exc}")
    st.stop()

try:
    account = _load_account()
except Exception:
    account = {}

positions = _normalise(raw_positions, account)
client_is_mobile = _client_is_mobile()
render_desktop_trades = client_is_mobile is not True
render_mobile_trades = client_is_mobile is not False
icon_lookup = icons.icon_urls(tuple(r.get("coin") for r in positions if r.get("coin")))
equity = float(account.get("equity") or 0)
total_upnl = sum(float(r.get("upnl") or 0) for r in positions)
total_notional = sum(float(r.get("notional") or 0) for r in positions)
total_margin = sum(float(r.get("margin_used") or 0) for r in positions)
longs = [r for r in positions if r.get("direction") == "Long"]
shorts = [r for r in positions if r.get("direction") == "Short"]
long_exposure = sum(float(r.get("notional") or 0) for r in longs)
short_exposure = sum(float(r.get("notional") or 0) for r in shorts)
avg_upnl = total_upnl / len(positions) if positions else 0
margin_pct = total_margin / equity * 100 if equity else 0
upnl_pct = total_upnl / total_margin * 100 if total_margin else 0
best = max(positions, key=lambda r: float(r.get("upnl") or 0), default=None)
worst = min(positions, key=lambda r: float(r.get("upnl") or 0), default=None)
max_notional = max([float(r.get("notional") or 0) for r in positions] or [1])
margin_bar_cls = "green" if margin_pct < 25 else "amber" if margin_pct < 50 else "red"
try:
    closed_trades = _load_closed_trades(3)
except Exception:
    closed_trades = []
market_symbols = tuple(dict.fromkeys(["BTCUSDT"] + [r.get("coin") for r in positions if r.get("coin")]))
market_candles = _load_market_candles(market_symbols)
relative_candles = _load_relative_strength_candles(market_symbols)
btc_ticker = _load_market_ticker("BTCUSDT")
btc_liquidation_map = _load_btc_liquidation_map()
try:
    sector_mtime = os.path.getmtime(SECTOR_MAP_PATH)
except OSError:
    sector_mtime = 0
sector_map = _load_sector_map(sector_mtime)
circuit = _circuit_breaker(closed_trades, equity)
market_risk = _portfolio_market_risk(positions, market_candles, relative_candles, btc_ticker, icon_lookup)
sector_risk = _sector_exposure(positions, sector_map, icon_lookup)
available_margin = float(account.get("available_margin") or 0)
long_exposure_pct = long_exposure / total_notional * 100 if total_notional else 0
short_exposure_pct = short_exposure / total_notional * 100 if total_notional else 0
available_margin_pct = available_margin / equity * 100 if equity else 0
btc_read = market_risk.get("btc") or {}
btc_tone = _tone(btc_read.get("tone"))
btc_24h = _pct(btc_read.get("ret_24"), True) if btc_read.get("ret_24") is not None else "—"
if btc_tone == "green":
    btc_structure_read = "Trend intact · structure supportive"
elif btc_tone == "red":
    btc_structure_read = "Structure broken · selling pressure rising"
elif btc_read.get("ret_24") is None:
    btc_structure_read = "Data limited · waiting for candles"
else:
    btc_structure_read = "Choppy structure"
btc_status_cell = (
    f"<div class='lt-metric btc-status-metric {{class_name}}'>"
    "<span class='lt-metric-cap'>BTC Status</span>"
    f"<span class='lt-btc-value {btc_tone}'>{_esc(btc_24h)} 24h</span>"
    f"<span class='lt-btc-read'>{_esc(btc_structure_read)}</span>"
    "</div>"
)
best_trend_icon = chrome._inline_icon("increase.svg")
worst_trend_icon = chrome._inline_icon("decrease.svg")
chart_icon = chrome._inline_icon("chart-2.svg")
best_tone = _cls(best.get("upnl") if best else None)
best_perf_icon = best_trend_icon if best_tone == "green" else worst_trend_icon

summary_html = f"""
<div class='lt-metrics'>
  <div class='lt-metric-grid'>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Open Positions</span>
      <div class='lt-metric-big'>{len(positions)}</div>
      <span class='lt-metric-icon'>{chart_icon}</span>
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Total Unrealized P&amp;L</span>
      <div class='lt-metric-big {_cls(total_upnl)}'>{_money(total_upnl, True)} <small>{_pct(upnl_pct, True)}</small></div>
      <span class='lt-metric-sub'>Today</span>
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Margin Used</span>
      <div class='lt-metric-big'>{_money(total_margin)}</div>
      <span class='lt-metric-sub'>{_pct(margin_pct)} of equity</span>
      {_progress(margin_pct, margin_bar_cls)}
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Available Margin</span>
      <div class='lt-metric-big'>{_money(available_margin) if available_margin else '—'}</div>
      <span class='lt-metric-sub'>{_pct(available_margin_pct)} of equity</span>
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Account Equity</span>
      <div class='lt-metric-big'>{_money(equity) if equity else '—'}</div>
      <span class='lt-metric-sub'>100% of equity</span>
    </div>
    {btc_status_cell.format(class_name='mobile-btc-status')}
  </div>
  <div class='lt-metric-grid secondary'>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Long Exposure</span>
      <div class='lt-metric-big green'>{_money(long_exposure)} <small>{_pct(long_exposure_pct)}</small></div>
      {_progress(long_exposure_pct, 'green')}
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Short Exposure</span>
      <div class='lt-metric-big red'>{_money(short_exposure)} <small>{_pct(short_exposure_pct)}</small></div>
      {_progress(short_exposure_pct, 'red')}
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Best Performer</span>
      <div class='lt-metric-performer'><div class='lt-metric-performer-main'>{_coin_icon(best.get('coin') or '', icon_lookup) if best else ''}<div><strong>{_esc(best.get('coin') if best else '—')}</strong><span class='{best_tone}'>{_money(best.get('upnl') if best else None, True)} &nbsp; {_pct(best.get('upnl_pct') if best else None, True)}</span></div></div><span class='lt-trend-icon {best_tone}'>{best_perf_icon}</span></div>
    </div>
    <div class='lt-metric'>
      <span class='lt-metric-cap'>Worst Performer</span>
      <div class='lt-metric-performer'><div class='lt-metric-performer-main'>{_coin_icon(worst.get('coin') or '', icon_lookup) if worst else ''}<div><strong>{_esc(worst.get('coin') if worst else '—')}</strong><span class='{_cls(worst.get('upnl') if worst else None)}'>{_money(worst.get('upnl') if worst else None, True)} &nbsp; {_pct(worst.get('upnl_pct') if worst else None, True)}</span></div></div><span class='lt-trend-icon red'>{worst_trend_icon}</span></div>
    </div>
    {btc_status_cell.format(class_name='desktop-btc-status')}
  </div>
</div>
"""
st.markdown(summary_html, unsafe_allow_html=True)

if st.session_state.get("live_tab") not in {"All Trades", "Long", "Short"}:
    st.session_state["live_tab"] = "All Trades"

group_options = ["None", "Direction", "Coin", "Profit / Loss", "Leverage", "Duration"]
sort_options = ["Unrealized P&L", "Size", "Entry", "Mark", "R Multiple", "Margin", "Liquidation", "Duration", "Leverage"]
default_cols = ["Coin", "Direction", "Size", "Entry", "Mark", "Unrealized P&L", "R Multiple", "Margin Used", "Liquidation Price", "TP / SL", "Duration"]
if st.session_state.get("live_group_by") not in group_options:
    st.session_state["live_group_by"] = "None"
if st.session_state.get("live_sort_by") not in sort_options:
    st.session_state["live_sort_by"] = "Unrealized P&L"
if "live_descending" not in st.session_state:
    st.session_state["live_descending"] = True
if not st.session_state.get("live_visible_cols"):
    st.session_state["live_visible_cols"] = default_cols

tab = st.session_state["live_tab"]
group_by = st.session_state["live_group_by"]
sort_by = st.session_state["live_sort_by"]
descending = st.session_state["live_descending"]
visible_cols = st.session_state["live_visible_cols"]
visible_cols = [
    "Unrealized P&L" if c == "Unrealised P&L" else "Duration" if c == "Age" else c
    for c in visible_cols
    if c != "Actions"
]

filtered = positions
if tab == "Long":
    filtered = longs
elif tab == "Short":
    filtered = shorts
filtered = _sort_rows(filtered, sort_by, descending)

st.markdown(
    """
<div class='advisor-head live-trades-head'>
  <div><b>LIVE TRADES</b></div>
</div>
""",
    unsafe_allow_html=True,
)

with st.container(key="live_tab_selector"):
    st.segmented_control(
        "Live trade filter",
        ["All Trades", "Long", "Short"],
        format_func=lambda v: f"{v} ({len(positions) if v == 'All Trades' else len(longs) if v == 'Long' else len(shorts)})",
        label_visibility="collapsed",
        key="live_tab",
    )

st.markdown("<div class='lt-panel'>", unsafe_allow_html=True)
if not positions:
    st.markdown(
        f"<div class='empty'><span class='empty-whale'>{chrome._inline_icon('whale-empty.svg')}</span><b>No open trades right now.</b><span>Open positions from Bybit will appear here automatically.</span></div>",
        unsafe_allow_html=True,
    )
else:
    headers = {
        "Coin": "<th>Coin</th>",
        "Direction": "<th>Direction</th>",
        "Size": "<th class='r'>Size<br><small>(USDT)</small></th>",
        "Entry": "<th class='r'>Entry<br><small>Price</small></th>",
        "Mark": "<th class='r'>Mark<br><small>Price</small></th>",
        "Unrealized P&L": "<th class='r'>Unrealized P&L<br><small>(USDT) &nbsp;&nbsp; %</small></th>",
        "R Multiple": "<th class='r'>R Multiple</th>",
        "Margin Used": "<th class='r'>Margin<br><small>Used</small></th>",
        "Liquidation Price": "<th class='r'>Liq. Price</th>",
        "TP / SL": "<th>TP / SL</th>",
        "Duration": "<th class='r'>Duration</th>",
    }
    if render_desktop_trades:
        table = ["<div class='desktop-table'><table class='lt-table'><thead><tr>"]
        table.extend(headers[c] for c in visible_cols)
        table.append("</tr></thead><tbody>")

        for group, rows in _group_rows(filtered, group_by):
            if group:
                table.append(f"<tr><td colspan='{len(visible_cols)}' class='muted' style='background:rgba(15,23,42,.35);font-weight:850'>{_esc(group)}</td></tr>")
            for row in rows:
                direction = row.get("direction")
                side_cls = "long" if direction == "Long" else "short"
                notional_pct = float(row.get("notional") or 0) / max_notional * 100 if max_notional else 0
                cells = {
                    "Coin": f"<td><div class='coin'>{_coin_icon(row.get('coin') or '', icon_lookup)}<div><span class='sym'>{_esc(row.get('coin'))}</span><span class='lev'>{float(row.get('leverage') or 0):g}x</span></div></div></td>",
                    "Direction": f"<td><span class='badge {side_cls}'>{_esc(direction)}</span></td>",
                    "Size": f"<td class='r'>{_money(row.get('notional'))}<div class='sizebar'>{_progress(notional_pct, 'green')}</div></td>",
                    "Entry": f"<td class='r'>{_price(row.get('entry'))}</td>",
                    "Mark": f"<td class='r'>{_price(row.get('mark'))}</td>",
                    "Unrealized P&L": f"<td class='r'><span class='{_cls(row.get('upnl'))}'>{_money(row.get('upnl'), True)}</span><br><span class='{_cls(row.get('upnl_pct'))}'>{_pct(row.get('upnl_pct'), True)}</span></td>",
                    "R Multiple": f"<td class='r'><span class='{_cls(row.get('r_multiple'))}'>{_r_label(row.get('r_multiple'))}</span></td>",
                    "Margin Used": f"<td class='r'>{_money(row.get('margin_used'))}<br><span class='muted'>{_pct(row.get('margin_pct_equity'))}</span></td>",
                    "Liquidation Price": f"<td class='r'><span class='{_liq_cls(row)}'>{_price(row.get('liq'))}</span></td>",
                    "TP / SL": f"<td class='tpcell'>{_tp_sl(row)}</td>",
                    "Duration": f"<td class='r'>{_age_label(row.get('age_h'))}</td>",
                }
                table.append("<tr>")
                table.extend(cells[c] for c in visible_cols)
                table.append("</tr>")
        table.append("</tbody></table></div>")
        st.markdown("".join(table), unsafe_allow_html=True)

    if render_mobile_trades:
        mobile = ["<div class='mobile-cards'>"]
        for row in filtered:
            direction = row.get("direction")
            side_cls = "long" if direction == "Long" else "short"
            mobile.append(
                f"<details class='mtrade'><summary class='mhead'><div class='coin'>{_coin_icon(row.get('coin') or '', icon_lookup)}"
                f"<div><span class='sym'>{_esc(row.get('coin'))}</span><span class='lev'>{float(row.get('leverage') or 0):g}x</span></div></div>"
                f"<span class='mtrade-side'><span class='badge {side_cls}'>{_esc(direction)}</span><span class='mchev'>⌄</span></span></summary>"
                f"<div class='mtrade-body'>"
                f"<div class='mgrid'>"
                f"<div class='mfield'><span>Unrealized P&L</span><b class='{_cls(row.get('upnl'))}'>{_money(row.get('upnl'), True)} · {_pct(row.get('upnl_pct'), True)}</b></div>"
                f"<div class='mfield'><span>Entry → Mark</span><b>{_price(row.get('entry'))} → {_price(row.get('mark'))}</b></div>"
                f"<div class='mfield'><span>Margin Used</span><b>{_money(row.get('margin_used'))} · {_pct(row.get('margin_pct_equity'))}</b></div>"
                f"<div class='mfield'><span>R Multiple</span><b class='{_cls(row.get('r_multiple'))}'>{_r_label(row.get('r_multiple'))}</b></div>"
                f"<div class='mfield'><span>Liquidation</span><b class='{_liq_cls(row)}'>{_price(row.get('liq'))}</b></div>"
                f"<div class='mfield'><span>Duration</span><b>{_age_label(row.get('age_h'))}</b></div>"
                f"</div><div style='margin-top:10px'>{_tp_sl(row)}</div></div></details>"
            )
        mobile.append("</div>")
        st.markdown("".join(mobile), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

if positions and render_desktop_trades:
    with st.container(key="live_controls"):
        controls = st.columns([0.18, 0.32, 0.28])
        with controls[0]:
            st.toggle("High → Low", key="live_descending")
        with controls[1]:
            st.selectbox(
                "Group by",
                group_options,
                format_func=lambda v: f"Group: {v}",
                label_visibility="collapsed",
                key="live_group_by",
            )
        with controls[2]:
            st.selectbox(
                "Sort by",
                sort_options,
                format_func=lambda v: f"Sort: {v}",
                label_visibility="collapsed",
                key="live_sort_by",
            )

st.markdown(_risk_cards_html(circuit, market_risk, sector_risk, icon_lookup, btc_liquidation_map), unsafe_allow_html=True)
