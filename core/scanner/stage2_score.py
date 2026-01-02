from __future__ import annotations

from core.config.constants import GRANULARITY_SECONDS
from core.config.settings import Settings
from core.data.bitget_client import BitgetClient
from core.features.indicators import ema, efficiency_ratio
from core.utils.math import safe_div


def score_stage2(
    client: BitgetClient, candidates: list[dict], settings: Settings
) -> tuple[list[dict], dict[str, object]]:
    scored: list[dict] = []
    candles_4h_cache: dict[str, object] = {}

    for candidate in candidates:
        symbol = candidate["symbol"]
        candles_4h = client.get_candles(
            symbol,
            GRANULARITY_SECONDS["4h"],
            settings.candles_limit,
            settings.product_type,
        )
        if candles_4h.empty or len(candles_4h) < 210:
            continue

        candles_1h = client.get_candles(
            symbol,
            GRANULARITY_SECONDS["1h"],
            settings.candles_limit,
            settings.product_type,
        )

        close_4h = candles_4h["close"]
        ema_fast = ema(close_4h, 50)
        ema_slow = ema(close_4h, 200)
        trend = safe_div(ema_fast.iloc[-1] - ema_slow.iloc[-1], ema_slow.iloc[-1])

        slope_index = max(1, settings.slope_lookback)
        slope = safe_div(
            ema_fast.iloc[-1] - ema_fast.iloc[-slope_index], ema_fast.iloc[-slope_index]
        )

        efficiency = (
            efficiency_ratio(candles_1h["close"])
            if not candles_1h.empty
            else efficiency_ratio(close_4h)
        )

        score = (
            settings.stage2_weight_trend * abs(trend)
            + settings.stage2_weight_slope * abs(slope)
            + settings.stage2_weight_efficiency * efficiency
        )

        scored.append(
            {
                "symbol": symbol,
                "score": score,
                "trend": trend,
                "slope": slope,
                "efficiency": efficiency,
            }
        )
        candles_4h_cache[symbol] = candles_4h

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: settings.top_k], candles_4h_cache

