from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone


def setup_state(row) -> str:
    classification = getattr(row, "classification", "")
    if classification == "Breakout Radar Priority":
        return "BREAKOUT_RADAR_PRIORITY"
    if classification == "High Watch":
        return "HIGH_WATCH"
    if classification == "Developing Setup":
        return "DEVELOPING_SETUP"
    if classification == "Early / Incomplete":
        return "EARLY_INCOMPLETE"
    if classification == "Ignore":
        return "IGNORE"
    if row.overall_score >= 85:
        return "BREAKOUT_RADAR_PRIORITY"
    if row.overall_score >= 75:
        return "HIGH_WATCH"
    if row.overall_score >= 65:
        return "DEVELOPING_SETUP"
    if row.overall_score >= 50:
        return "EARLY_INCOMPLETE"
    return "IGNORE"


def should_alert(row, config: dict, state: dict) -> tuple[bool, str]:
    alerts = config.get("alerts", {})
    state_name = setup_state(row)
    if not alerts.get("enabled", False):
        return False, "alerts disabled"
    if row.overall_score < float(alerts.get("min_overall_score", 75)):
        return False, "overall score below alert threshold"
    if row.compression_score < float(alerts.get("min_compression_score", 70)):
        return False, "compression below alert threshold"
    if row.structural_pressure_score < float(alerts.get("min_structure_score", 70)):
        return False, "structure below alert threshold"
    if row.participation_score < float(alerts.get("min_participation_score", 50)):
        return False, "participation below alert threshold"
    if row.price_acceptance_score < float(alerts.get("min_acceptance_score", 50)):
        return False, "acceptance below alert threshold"
    max_distance = alerts.get("max_distance_to_resistance_pct")
    if max_distance is not None and row.distance_to_resistance_pct is not None:
        if row.distance_to_resistance_pct > float(max_distance):
            return False, "too far from resistance"
    previous = state.get(row.symbol, {})
    if alerts.get("state_change_only", True) and previous.get("last_state") == state_name:
        return False, "state unchanged"
    last_alert_at = previous.get("last_alert_at")
    if last_alert_at:
        cooldown = timedelta(hours=float(alerts.get("cooldown_hours", 6)))
        try:
            last_dt = datetime.fromisoformat(last_alert_at)
            if datetime.now(timezone.utc) - last_dt < cooldown:
                return False, "alert cooldown active"
        except ValueError:
            pass
    return True, state_name


def format_alert(row) -> str:
    entry, stop, tp1, tp2, rr1, rr2 = _trade_map(row)
    return "\n".join(
        [
            f"<b>BREAKOUT RADAR: {_esc(row.symbol)}</b>",
            f"{_esc(row.classification)} · {row.overall_score:.1f} / 100",
            f"Bybit: <a href=\"{_bybit_url(row.symbol)}\">{_esc(row.symbol)} Perp</a>",
            "",
            f"<b>Situation:</b> {_esc(_situation(row))}",
            f"<b>Bias:</b> {_esc(_bias(row))}",
            "",
            "<b>Trade map:</b>",
            f"Entry: {_fmt_price(entry)}",
            f"Stop: {_fmt_price(stop)}",
            f"TP1: {_fmt_price(tp1)} · R:R {_fmt_rr(rr1)}",
            f"TP2: {_fmt_price(tp2)} · R:R {_fmt_rr(rr2)}",
            "",
            "<b>Trade conditions:</b>",
            f"Trigger: {_esc(_trigger_immediacy(row))}",
            f"Entry: {_esc(_entry_condition(row))}",
            f"Invalid: {_esc(_invalidation_condition(row))}",
            f"Pressure: {_esc(_pressure(row))}",
            f"BTC: {_esc(_btc_correlation(row))}",
            f"Pace: {_esc(_pace(row))}",
            "",
            f"<b>Verdict:</b> {_esc(_verdict(row, rr1, rr2))}",
            "",
            f"<b>Best case:</b> {_esc(_best_case(row))}",
            f"<b>Failure case:</b> {_esc(_failure_case(row))}",
        ]
    )


def _trade_map(row) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    entry = row.breakout_level_resistance or row.current_price
    stop = row.invalidated_below
    target = None
    try:
        target = row.raw_metrics.get("magnitude", {}).get("Realistic Target", {}).get("raw")
    except AttributeError:
        target = None
    if target is None:
        target = row.breakout_level_resistance
    tp2 = float(target) if target else None
    tp1 = (entry + (tp2 - entry) * 0.5) if entry and tp2 and tp2 > entry else None
    rr1 = _rr(entry, stop, tp1)
    rr2 = _rr(entry, stop, tp2)
    return entry, stop, tp1, tp2, rr1, rr2


def _rr(entry: float | None, stop: float | None, target: float | None) -> float | None:
    if not entry or not stop or not target:
        return None
    risk = entry - stop
    reward = target - entry
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _entry_condition(row) -> str:
    trigger = _fmt_price(row.breakout_level_resistance)
    if row.participation_score >= 70:
        return f"1H close above {trigger}, or retest hold with participation intact."
    if row.price_acceptance_score >= 60:
        return f"1H close above {trigger} without rejection."
    return f"1H close above {trigger}, or retest hold with RVOL improving."


def _trigger_immediacy(row) -> str:
    resistance = row.breakout_level_resistance
    price = row.current_price
    atr = _raw_metric(row, "magnitude", "ATR")
    distance_atr = ((resistance - price) / atr) if resistance and price and atr else None
    near_resistance = _raw_metric(row, "structural_pressure", "Time Near Resistance")
    rvol = _raw_metric(row, "participation", "Relative Volume")
    if distance_atr is not None and distance_atr < -0.25:
        return "Overrun. Price is already through resistance; do not chase, only clean retest matters."
    if distance_atr is not None and distance_atr <= 0.35 and row.participation_score >= 65:
        return f"Loaded. Price is {distance_atr:.2f} ATR below resistance; volume follow-through matters now."
    if distance_atr is not None and distance_atr <= 0.60 and row.structural_pressure_score >= 65:
        help_text = _trigger_help(row, distance_atr, near_resistance, rvol)
        return f"Pressing. Price is {distance_atr:.2f} ATR below resistance; needs {help_text}"
    if distance_atr is not None:
        help_text = _trigger_help(row, distance_atr, near_resistance, rvol)
        return f"Building. Price is {distance_atr:.2f} ATR below resistance; needs {help_text}"
    return "Building. ATR/trigger data incomplete; needs clean closes near resistance with RVOL improving."


def _trigger_help(row, distance_atr: float | None, near_resistance: float | None, rvol: float | None) -> str:
    if distance_atr is not None and distance_atr > 0.60:
        return "price to move within 0.3 ATR of resistance."
    if near_resistance is not None and near_resistance < 20:
        return "more 1H closes clustered near resistance."
    if rvol is not None and rvol < 1.3:
        return "RVOL above 1.3 while price holds near trigger."
    if row.price_acceptance_score < 60:
        return "stronger acceptance, ideally closes near candle highs."
    return "continued hold near trigger without rejection."


def _invalidation_condition(row) -> str:
    invalid = _fmt_price(row.invalidated_below)
    if row.price_acceptance_score < 55:
        return f"Close below {invalid}, or loss of VWAP + back inside base."
    return f"Close below {invalid}, or failed breakout closing back inside range."


def _pressure(row) -> str:
    taker_buy = _raw_metric(row, "smart_money", "Taker Buy Ratio")
    oi = _raw_metric(row, "smart_money", "Open Interest Change 1H")
    if taker_buy is not None:
        if taker_buy >= 55:
            return "Taker buys leading; buyers need to absorb offers at trigger."
        if taker_buy >= 52:
            return "Slight buy pressure; trigger still needs absorption."
        if taker_buy < 48:
            return "Sell pressure still present; breakout needs buyer absorption."
    if oi is not None and oi >= 2 and row.momentum_score >= 55:
        return "Leveraged interest building with price pressure; watch for absorption at trigger."
    if row.structural_pressure_score >= 70 and row.participation_score >= 60:
        return "Candle/volume pressure leans bid-side; order book unavailable."
    return "Order book unavailable; using candle/volume pressure only."


def _btc_correlation(row) -> str:
    context = {}
    try:
        context = row.raw_metrics.get("market_context", {}) or {}
    except AttributeError:
        pass
    corr = context.get("correlation_1h")
    btc_change = context.get("benchmark_change_pct")
    relationship = context.get("relationship") or "unavailable"
    if corr is None:
        return "Unavailable."
    label = {
        "btc drag risk": "High correlation. If BTC keeps falling, this setup is less likely to follow.",
        "btc tailwind": "High correlation. If BTC keeps rising, this setup has market support behind it.",
        "idiosyncratic strength": "Low correlation. This coin is moving more on its own.",
        "low btc dependence": "Low correlation. BTC is less useful as a guide here.",
        "moderate btc link": "Moderate correlation. BTC matters, but the coin's own structure still leads.",
    }.get(relationship, relationship)
    btc_bit = f" BTC {btc_change:+.2f}%." if btc_change is not None else ""
    return f"{label} 1H corr {corr:.2f}.{btc_bit}"


def _pace(row) -> str:
    distance = row.distance_to_resistance_pct
    fast = row.momentum_score >= 70 and row.participation_score >= 70
    slow = row.momentum_score < 55 or row.participation_score < 55 or row.price_acceptance_score < 55
    if distance is not None and distance <= 1.5 and fast:
        return "Setup is close. Could trigger in the next few 1H candles if volume follows through."
    if distance is not None and distance <= 3 and not slow:
        return "Setup is close, but timing depends on acceptance and volume follow-through."
    if distance is not None and distance <= 6:
        return "Still building. Needs more pressure near resistance before timing matters."
    if distance is not None and distance < -1:
        return "Extended past trigger. Only valid on a clean retest."
    if row.price_acceptance_score < 55:
        return "Early. Acceptance is too weak to estimate timing."
    return "Timing unclear. Let the trigger and invalidation levels lead."


def _situation(row) -> str:
    location = _location_read(row)
    edge = _edge_read(row)
    drag = _drag_read(row)
    return f"{location} {edge} {drag}"


def _bias(row) -> str:
    trigger = _fmt_price(row.breakout_level_resistance)
    distance = row.distance_to_resistance_pct
    if distance is not None and distance < -0.25:
        if row.price_acceptance_score >= 60:
            return f"Already through {trigger}; only interested if it holds the level instead of snapping back inside."
        return f"Through {trigger}, but the hold is not clean enough to chase."
    if row.participation_score >= 70 and row.structural_pressure_score >= 65:
        return f"Constructive. A firm 1H close through {trigger} has enough participation to matter."
    if row.compression_score >= 75 and row.participation_score < 45:
        return f"Watchlist, not trigger-ready. The chart is tight, but it needs buyers to show up before {trigger} matters."
    if row.price_acceptance_score < 55:
        return f"Early. Price needs cleaner closes near {trigger}; otherwise this can stay noisy."
    if row.momentum_score < 45:
        return f"Slow build. Structure is there, but it needs impulse before treating {trigger} as live."
    return f"Constructive, but confirmation still has to come from a clean break or retest around {trigger}."


def _location_read(row) -> str:
    distance = row.distance_to_resistance_pct
    resistance = _fmt_price(row.breakout_level_resistance)
    symbol = row.symbol.upper()
    if distance is None:
        return f"{symbol} has a developing breakout shape, but the trigger level is not cleanly mapped."
    if abs(distance) < 0.15:
        return f"{symbol} is sitting right on the mapped trigger at {resistance}."
    if distance < -1:
        return f"{symbol} has already pushed {abs(distance):.1f}% beyond the mapped trigger at {resistance}."
    if distance < -0.15:
        return f"{symbol} is just through the mapped trigger at {resistance}."
    if distance <= 1:
        return f"{symbol} is parked {distance:.1f}% under resistance at {resistance}."
    if distance <= 3:
        return f"{symbol} is within {distance:.1f}% of resistance at {resistance}."
    return f"{symbol} is still {distance:.1f}% below resistance at {resistance}."


def _edge_read(row) -> str:
    strongest = getattr(row, "strongest_engine", "")
    if strongest == "Compression":
        if row.structural_pressure_score >= 70:
            return "The read is a tight base with structure pressing the level."
        return "The read is mostly compression: tight, but not fully proven structurally."
    if strongest == "Structural Pressure":
        return "The read is structural pressure: repeated work near the level rather than a random pop."
    if strongest == "Participation":
        return "The read is participation-led, which means volume/flow is doing more than just price drifting higher."
    if strongest == "Momentum":
        return "The read is impulse-led, so follow-through matters more than patience here."
    if strongest == "Price Acceptance":
        return "The read is acceptance-led: candles are holding the area better than they are rejecting it."
    if strongest == "Smart Money":
        return "The read is derivatives-led, with positioning adding weight to the setup."
    if row.compression_score >= 70 and row.structural_pressure_score >= 65:
        return "The read is a compressed structure leaning into resistance."
    return "The read is still mixed rather than clean."


def _drag_read(row) -> str:
    if row.participation_score < 45:
        return "The issue is participation: buyers have not properly stepped in yet."
    if row.price_acceptance_score < 55:
        return "The issue is acceptance: price has not held the area cleanly enough yet."
    if row.momentum_score < 45:
        return "The issue is pace: the setup is forming, but impulse is still thin."
    if row.structural_pressure_score < 60:
        return "The issue is structure: the level needs cleaner pressure before it deserves more attention."
    if row.compression_score < 60:
        return "The issue is expansion: it is not as tight as a proper coil should be."
    return "There is no obvious single failure point; the next candle quality matters."


def _best_case(row) -> str:
    if row.participation_score >= 70:
        return "Holds near resistance, participation stays constructive, closes through trigger."
    return "Holds near resistance, volume improves, closes through trigger."


def _failure_case(row) -> str:
    if row.price_acceptance_score < 55:
        return "Wicks above resistance, loses VWAP, or drops below base."
    return "Rejects at the trigger, closes back inside the range, or loses invalidation."


def _verdict(row, rr1: float | None, rr2: float | None) -> str:
    if rr2 is None:
        return "Watch the setup, but trade map is incomplete until target and invalidation are clear."
    if rr2 < 1.5:
        return "Setup may be forming, but the mapped reward does not yet justify the risk."
    if rr1 is not None and rr1 < 1.0:
        return "Watchable, but TP1 does not pay enough unless entry improves or stop tightens."
    if row.price_acceptance_score < 55:
        return "Good structure, but wait for acceptance to improve before treating it as actionable."
    return "Trade map is reasonable if price confirms through the trigger without rejection."


def _raw_metric(row, engine: str, name: str) -> float | None:
    try:
        value = row.raw_metrics.get(engine, {}).get(name, {}).get("raw")
    except AttributeError:
        return None
    if isinstance(value, dict):
        for key in ("buy_pct", "oi_change_pct", "price_change_pct"):
            if key in value:
                return _to_float(value.get(key))
        return None
    return _to_float(value)


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bybit_url(symbol: str) -> str:
    return f"https://www.bybit.com/trade/usdt/{symbol.upper()}"


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _icon(score: float) -> str:
    if score >= 70:
        return "✅"
    if score >= 50:
        return "⚠"
    return "❌"


def _score_cell(score: float) -> str:
    return f"{_icon(score)} {_whole(score)}"


def _whole(score: float) -> int:
    return int(round(float(score or 0)))


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "—"
    value = float(value)
    if abs(value) >= 1:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if abs(value) >= 0.01:
        return f"{value:.5f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _fmt_rr(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"
