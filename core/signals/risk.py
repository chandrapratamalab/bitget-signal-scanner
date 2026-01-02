from __future__ import annotations

import math

import pandas as pd

from core.features.indicators import atr
from core.features.swing import recent_swing_high, recent_swing_low


def compute_risk(
    direction: str,
    candles_15m: pd.DataFrame,
    entry_plan: dict,
    atr_period: int,
    atr_mult: float,
    swing_lookback: int,
) -> dict | None:
    if not entry_plan or candles_15m is None or candles_15m.empty:
        return None

    atr_series = atr(candles_15m, atr_period)
    atr_value = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
    if math.isnan(atr_value):
        atr_value = 0.0

    entry_low = float(entry_plan["entry_zone_low"])
    entry_high = float(entry_plan["entry_zone_high"])
    entry_price = float(entry_plan["entry_price"])

    if direction == "LONG":
        swing_low = recent_swing_low(candles_15m, swing_lookback)
        sl_atr = entry_low - atr_mult * atr_value
        sl_swing = swing_low if swing_low > 0 else sl_atr
        sl = min(sl_atr, sl_swing) if atr_value > 0 else sl_swing
        sl_reason = "ATR" if sl == sl_atr else "swing"
        risk = entry_price - sl
        if risk <= 0:
            return None
        tp1 = entry_price + risk
        tp2 = entry_price + 2 * risk
    else:
        swing_high = recent_swing_high(candles_15m, swing_lookback)
        sl_atr = entry_high + atr_mult * atr_value
        sl_swing = swing_high if swing_high > 0 else sl_atr
        sl = max(sl_atr, sl_swing) if atr_value > 0 else sl_swing
        sl_reason = "ATR" if sl == sl_atr else "swing"
        risk = sl - entry_price
        if risk <= 0:
            return None
        tp1 = entry_price - risk
        tp2 = entry_price - 2 * risk

    return {
        "sl": sl,
        "sl_reason": sl_reason,
        "tp1": tp1,
        "tp2": tp2,
    }

