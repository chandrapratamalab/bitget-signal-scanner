from __future__ import annotations

import pandas as pd

from core.features.indicators import ema
from core.utils.math import safe_div


def evaluate_setup(
    candles_1h: pd.DataFrame | None,
    direction: str,
    value_max_dist_pct: float = 0.02,
    spike_lookback: int = 20,
    spike_mult: float = 2.5,
) -> dict:
    if candles_1h is None or candles_1h.empty or len(candles_1h) < 60:
        return {
            "setup_ok": True,
            "setup_reason": "no_1h_data",
            "key_level": None,
        }

    close = candles_1h["close"]
    ema_fast = ema(close, 20)
    ema_slow = ema(close, 50)

    last_close = float(close.iloc[-1])
    ema_fast_last = float(ema_fast.iloc[-1])
    ema_slow_last = float(ema_slow.iloc[-1])

    trend_ok = False
    if direction == "LONG":
        trend_ok = last_close > ema_slow_last and ema_fast_last > ema_slow_last
    elif direction == "SHORT":
        trend_ok = last_close < ema_slow_last and ema_fast_last < ema_slow_last

    dist_fast = abs(safe_div(last_close - ema_fast_last, ema_fast_last))
    dist_slow = abs(safe_div(last_close - ema_slow_last, ema_slow_last))
    value_dist = min(dist_fast, dist_slow)
    pullback_ok = value_dist <= value_max_dist_pct

    ranges = candles_1h["high"] - candles_1h["low"]
    avg_range = float(ranges.tail(spike_lookback).mean()) if len(ranges) >= spike_lookback else float(ranges.mean())
    last_range = float(ranges.iloc[-1])
    spike = avg_range > 0 and last_range > avg_range * spike_mult

    reasons: list[str] = []
    if not trend_ok:
        reasons.append("trend_misaligned")
    if not pullback_ok:
        reasons.append("not_near_value")
    if spike:
        reasons.append("1h_spike")

    setup_ok = trend_ok and pullback_ok and not spike
    reason = "ok" if setup_ok else ", ".join(reasons)
    key_level = (ema_fast_last + ema_slow_last) / 2

    return {
        "setup_ok": setup_ok,
        "setup_reason": reason,
        "key_level": key_level,
    }
