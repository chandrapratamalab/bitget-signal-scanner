from __future__ import annotations

import pandas as pd

from core.features.indicators import ema
from core.utils.math import safe_div


def detect_regime(candles_4h: pd.DataFrame, slope_lookback: int) -> dict:
    if candles_4h is None or candles_4h.empty or len(candles_4h) < 210:
        return {"regime": "NO_TRADE", "direction": "NO_TRADE"}

    close = candles_4h["close"]
    ema_fast = ema(close, 50)
    ema_slow = ema(close, 200)
    slope_index = max(1, slope_lookback)

    ema_fast_last = ema_fast.iloc[-1]
    ema_slow_last = ema_slow.iloc[-1]
    ema_fast_prev = ema_fast.iloc[-slope_index]

    slope = safe_div(ema_fast_last - ema_fast_prev, ema_fast_prev)

    if ema_fast_last > ema_slow_last and slope > 0:
        return {"regime": "TREND_UP", "direction": "LONG", "slope": slope}
    if ema_fast_last < ema_slow_last and slope < 0:
        return {"regime": "TREND_DOWN", "direction": "SHORT", "slope": slope}

    return {"regime": "RANGE", "direction": "NO_TRADE", "slope": slope}

