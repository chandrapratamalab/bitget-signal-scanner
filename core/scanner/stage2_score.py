from __future__ import annotations

from core.config.constants import GRANULARITY_SECONDS
from core.config.settings import Settings, resolve_timeframes
from core.data.bitget_client import BitgetClient
from core.features.indicators import ema, efficiency_ratio
from core.utils.math import safe_div


def score_stage2(
    client: BitgetClient,
    candidates: list[dict],
    settings: Settings,
    limit: int | None = None,
) -> tuple[list[dict], dict[str, dict[str, object]]]:
    scored: list[dict] = []
    candles_cache: dict[str, dict[str, object]] = {}
    timeframes = resolve_timeframes(settings)
    bias_tf = timeframes["bias_tf"]
    confirm_tf = timeframes["confirm_tf"]

    for candidate in candidates:
        symbol = candidate["symbol"]
        candles_bias = client.get_candles(
            symbol,
            GRANULARITY_SECONDS[bias_tf],
            settings.candles_limit,
            settings.product_type,
        )
        if candles_bias.empty or len(candles_bias) < 210:
            continue

        candles_confirm = candles_bias
        if confirm_tf != bias_tf:
            candles_confirm = client.get_candles(
                symbol,
                GRANULARITY_SECONDS[confirm_tf],
                settings.candles_limit,
                settings.product_type,
            )

        close_bias = candles_bias["close"]
        ema_fast = ema(close_bias, 50)
        ema_slow = ema(close_bias, 200)
        trend = safe_div(ema_fast.iloc[-1] - ema_slow.iloc[-1], ema_slow.iloc[-1])

        slope_index = max(1, settings.slope_lookback)
        slope = safe_div(
            ema_fast.iloc[-1] - ema_fast.iloc[-slope_index], ema_fast.iloc[-slope_index]
        )

        efficiency = (
            efficiency_ratio(candles_confirm["close"])
            if not candles_confirm.empty
            else efficiency_ratio(close_bias)
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
        candles_cache.setdefault(bias_tf, {})[symbol] = candles_bias
        if confirm_tf != bias_tf and candles_confirm is not None:
            candles_cache.setdefault(confirm_tf, {})[symbol] = candles_confirm

    scored.sort(key=lambda item: item["score"], reverse=True)
    if limit is not None:
        scored = scored[: limit]
    return scored, candles_cache
