from __future__ import annotations

import pandas as pd

from core.config.settings import Settings
from core.signals.entry_rules import build_entry_plan
from core.signals.regime import detect_regime
from core.signals.risk import compute_risk
from core.utils.time import now_utc_iso


def generate_signal(
    symbol: str,
    candles_4h: pd.DataFrame,
    candles_15m: pd.DataFrame,
    settings: Settings,
) -> dict | None:
    regime_info = detect_regime(candles_4h, settings.slope_lookback)
    direction = regime_info.get("direction", "NO_TRADE")
    if direction == "NO_TRADE":
        return None

    entry_plan = build_entry_plan(
        direction,
        candles_15m,
        settings.swing_lookback,
        settings.entry_buffer_pct,
    )
    if not entry_plan:
        return None

    risk = compute_risk(
        direction,
        candles_15m,
        entry_plan,
        settings.atr_period,
        settings.atr_mult,
        settings.swing_lookback,
    )
    if not risk:
        return None

    return {
        "symbol": symbol,
        "regime": regime_info.get("regime", "NO_TRADE"),
        "direction": direction,
        "entry_type": entry_plan["entry_type"],
        "entry_zone_low": entry_plan["entry_zone_low"],
        "entry_zone_high": entry_plan["entry_zone_high"],
        "entry_price": entry_plan["entry_price"],
        "entry_when": entry_plan["entry_when"],
        "entry_status": entry_plan["entry_status"],
        "entry_time": entry_plan["entry_time"],
        "sl": risk["sl"],
        "sl_reason": risk["sl_reason"],
        "tp1": risk["tp1"],
        "tp2": risk["tp2"],
        "invalidation": entry_plan["invalidation"],
        "generated_at": now_utc_iso(),
    }

