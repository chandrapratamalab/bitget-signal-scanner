from __future__ import annotations

import pandas as pd

from core.features.swing import recent_swing_high, recent_swing_low
from core.utils.time import to_datetime_ms


def build_entry_plan(
    direction: str,
    candles_15m: pd.DataFrame,
    swing_lookback: int,
    entry_buffer_pct: float,
) -> dict | None:
    if direction == "NO_TRADE" or candles_15m is None or candles_15m.empty:
        return None

    last_close = float(candles_15m["close"].iloc[-1])
    last_ts = int(candles_15m["ts"].iloc[-1])
    entry_time = to_datetime_ms(last_ts).isoformat()

    if direction == "LONG":
        level = recent_swing_high(candles_15m, swing_lookback)
        zone_low = level * (1 - entry_buffer_pct)
        zone_high = level * (1 + entry_buffer_pct)
        entry_when = f"15m close breaks above {level:.4f} then retests zone"
        invalidation = "15m close back below entry zone"
    else:
        level = recent_swing_low(candles_15m, swing_lookback)
        zone_low = level * (1 - entry_buffer_pct)
        zone_high = level * (1 + entry_buffer_pct)
        entry_when = f"15m close breaks below {level:.4f} then retests zone"
        invalidation = "15m close back above entry zone"

    entry_mid = (zone_low + zone_high) / 2
    entry_status = "NOW" if zone_low <= last_close <= zone_high else "WAIT"

    return {
        "entry_type": "BREAK_RETEST",
        "entry_zone_low": zone_low,
        "entry_zone_high": zone_high,
        "entry_price": entry_mid,
        "entry_when": entry_when,
        "entry_status": entry_status,
        "entry_time": entry_time,
        "invalidation": invalidation,
    }

