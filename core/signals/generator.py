from __future__ import annotations

import pandas as pd

from core.config.settings import Settings
from core.signals.entry_rules import build_entry_plan
from core.signals.leverage import recommend_leverage_cap
from core.signals.regime import detect_regime
from core.signals.risk import compute_risk
from core.signals.setup import evaluate_setup
from core.utils.time import now_utc_iso


def generate_signal(
    symbol: str,
    candles_4h: pd.DataFrame,
    candles_1h: pd.DataFrame | None,
    candles_15m: pd.DataFrame,
    settings: Settings,
    market_context: dict | None = None,
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

    setup = evaluate_setup(candles_1h, direction)

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
        "sl_distance_pct": leverage["sl_distance_pct"],
        "atr_15m": leverage["atr_15m"],
        "atr_pct": leverage["atr_pct"],
        "recommended_leverage_cap": leverage["recommended_leverage_cap"],
        "recommended_leverage_cap_reason": leverage["recommended_leverage_cap_reason"],
        "setup_ok": setup["setup_ok"],
        "setup_reason": setup["setup_reason"],
        "key_level": setup["key_level"],
        "invalidation": entry_plan["invalidation"],
        "generated_at": now_utc_iso(),
    }
