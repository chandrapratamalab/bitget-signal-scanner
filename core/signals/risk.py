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

    entry_price = float(entry_plan["entry_price"])

    if direction == "LONG":
        swing_low = recent_swing_low(candles_15m, swing_lookback)
        sl = None
        if swing_low > 0:
            if atr_value > 0:
                sl = swing_low - atr_mult * atr_value
                sl_reason = "swing_atr"
            else:
                sl = swing_low
                sl_reason = "swing"
        elif atr_value > 0:
            sl = entry_price - atr_mult * atr_value
            sl_reason = "atr"
        else:
            return None
        if sl <= 0:
            return None
        risk = entry_price - sl
        if risk <= 0:
            return None
        tp1 = entry_price + risk
        tp2 = entry_price + 2 * risk
    else:
        swing_high = recent_swing_high(candles_15m, swing_lookback)
        sl = None
        if swing_high > 0:
            if atr_value > 0:
                sl = swing_high + atr_mult * atr_value
                sl_reason = "swing_atr"
            else:
                sl = swing_high
                sl_reason = "swing"
        elif atr_value > 0:
            sl = entry_price + atr_mult * atr_value
            sl_reason = "atr"
        else:
            return None
        if sl <= 0:
            return None
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
        "atr_15m": atr_value,
    }
