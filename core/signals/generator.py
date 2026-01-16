from __future__ import annotations

import pandas as pd

from core.config.constants import GRANULARITY_SECONDS
from core.config.settings import SCAN_MODE_SCALP, Settings, resolve_timeframes
from core.signals.entry_rules import build_entry_plan
from core.signals.leverage import recommend_leverage_cap
from core.signals.market_filters import analyze_market_conditions
from core.signals.regime import detect_regime
from core.signals.risk import compute_risk
from core.signals.setup import evaluate_setup
from core.utils.math import clamp
from core.utils.time import now_utc_iso


def generate_signal(
    symbol: str,
    candles_by_tf: dict[str, pd.DataFrame],
    settings: Settings,
    market_context: dict | None = None,
    funding_rate: float | None = None,
    open_interest: float | None = None,
    oi_change_pct: float | None = None,
) -> dict | None:
    timeframes = resolve_timeframes(settings)
    bias_tf = timeframes["bias_tf"]
    confirm_tf = timeframes["confirm_tf"]
    trigger_tf = timeframes["trigger_tf"]

    candles_bias = candles_by_tf.get(bias_tf)
    candles_confirm = candles_by_tf.get(confirm_tf)
    candles_trigger = candles_by_tf.get(trigger_tf)

    regime_info = detect_regime(candles_bias, settings.slope_lookback)
    direction = regime_info.get("direction", "NO_TRADE")
    if direction == "NO_TRADE":
        return None

    alignment_ok = True
    if (
        timeframes["scan_mode"] != SCAN_MODE_SCALP
        and settings.strict_trend_alignment
        and candles_confirm is not None
    ):
        confirm_regime = detect_regime(candles_confirm, settings.slope_lookback)
        confirm_direction = confirm_regime.get("direction", "NO_TRADE")
        if confirm_direction != direction:
            alignment_ok = False

    entry_plan = build_entry_plan(
        direction,
        candles_trigger,
        settings.swing_lookback,
        settings.entry_buffer_pct,
        GRANULARITY_SECONDS[trigger_tf],
    )
    if not entry_plan:
        return None

    risk = compute_risk(
        direction,
        candles_trigger,
        entry_plan,
        settings.atr_period,
        settings.atr_mult,
        settings.swing_lookback,
    )
    if not risk:
        return None

    setup = evaluate_setup(candles_confirm, direction)

    market_flags = analyze_market_conditions(
        direction,
        candles_trigger,
        funding_rate,
        oi_change_pct,
        settings,
        market_context,
    )
    risk_flags = list(market_flags["risk_flags"])
    if not alignment_ok:
        risk_flags.append("trend_misaligned")

    spread_pct = None
    quote_volume = None
    if market_context:
        spread_pct = market_context.get("spread")
        quote_volume = market_context.get("quote_volume")

    leverage = recommend_leverage_cap(
        symbol=symbol,
        entry_price=entry_plan["entry_price"],
        sl_price=risk["sl"],
        atr_15m=risk["atr_15m"],
        regime=regime_info.get("regime", "NO_TRADE"),
        spread_pct=spread_pct,
        quote_volume=quote_volume,
    )

    setup_type = "A"
    breakout_direction = market_flags.get("breakout_direction")
    if market_flags["crowded_long"] and direction == "SHORT":
        if breakout_direction == direction:
            setup_type = "B"
    elif market_flags["crowded_short"] and direction == "LONG":
        if breakout_direction == direction:
            setup_type = "B"

    entry_status = entry_plan["entry_status"]
    block_reasons: list[str] = []
    if timeframes["scan_mode"] == SCAN_MODE_SCALP:
        if settings.use_funding_filter and (
            market_flags["crowded_long"] or market_flags["crowded_short"]
        ):
            block_reasons.append("funding")
        if settings.use_oi_confirmation and not market_flags["oi_confirm"]:
            block_reasons.append("oi_confirm")
        if settings.use_overextension_filter and market_flags["overextended"]:
            block_reasons.append("overextended")

    if settings.strict_filters:
        if market_flags["overextended"]:
            block_reasons.append("overextended")
        if market_flags["late_move"]:
            block_reasons.append("late_move")
        if market_flags["thin_liquidity"]:
            block_reasons.append("thin_liquidity")
        if market_flags["oi_divergence"]:
            block_reasons.append("oi_divergence")
        if market_flags["crowded_long"] or market_flags["crowded_short"]:
            block_reasons.append("crowded")
        if not alignment_ok:
            block_reasons.append("trend_misaligned")

    if block_reasons:
        entry_status = "WAIT"
        hard_block = market_flags["thin_liquidity"] or (
            (market_flags["crowded_long"] or market_flags["crowded_short"])
            and market_flags["overextended"]
        )
        if hard_block or (settings.strict_filters and len(block_reasons) >= 2):
            entry_status = "NO_TRADE"

    confidence_score = 55
    if setup["setup_ok"]:
        confidence_score += 10
    else:
        confidence_score -= 10
    if market_flags["oi_confirm"]:
        confidence_score += 10
    if market_flags["early_pump_dump_ready"]:
        confidence_score += 5
    if alignment_ok:
        confidence_score += 5
    confidence_score -= len(risk_flags) * 7
    confidence_score = int(clamp(confidence_score, 0, 100))

    generated_at = now_utc_iso()
    entry_zone = f"{entry_plan['entry_zone_low']:.4f}-{entry_plan['entry_zone_high']:.4f}"
    return {
        "symbol": symbol,
        "scan_mode": timeframes["scan_mode"],
        "regime": regime_info.get("regime", "NO_TRADE"),
        "direction": direction,
        "setup_type": setup_type,
        "entry_type": entry_plan["entry_type"],
        "entry_zone_low": entry_plan["entry_zone_low"],
        "entry_zone_high": entry_plan["entry_zone_high"],
        "entry_zone": entry_zone,
        "entry_price": entry_plan["entry_price"],
        "entry_when": entry_plan["entry_when"],
        "entry_status": entry_status,
        "entry_time": entry_plan["entry_time"],
        "sl": risk["sl"],
        "sl_reason": risk["sl_reason"],
        "tp1": risk["tp1"],
        "tp2": risk["tp2"],
        "sl_distance_pct": leverage["sl_distance_pct"],
        "atr_15m": leverage["atr_15m"],
        "atr_pct": leverage["atr_pct"],
        "recommended_leverage_cap": leverage["recommended_leverage_cap"],
        "recommended_leverage_cap_reason": leverage["recommended_leverage_cap_reason"],
        "setup_ok": setup["setup_ok"],
        "setup_reason": setup["setup_reason"],
        "key_level": setup["key_level"],
        "invalidation": entry_plan["invalidation"],
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "oi_change_pct": oi_change_pct,
        "risk_flags": risk_flags,
        "confidence_score": confidence_score,
        "early_pump_dump_ready": market_flags["early_pump_dump_ready"],
        "generated_at": generated_at,
        "signal_time": generated_at,
    }
