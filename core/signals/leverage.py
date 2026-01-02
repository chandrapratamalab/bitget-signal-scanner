from __future__ import annotations

from core.utils.math import clamp


ALLOWED_LEVERAGE_STEPS = [1, 2, 3, 5, 7, 10]


def _round_down_to_allowed(value: float) -> float:
    chosen = ALLOWED_LEVERAGE_STEPS[0]
    for step in ALLOWED_LEVERAGE_STEPS:
        if step <= value:
            chosen = step
        else:
            break
    return float(chosen)


def _asset_class_cap(symbol: str, quote_volume: float | None, spread_pct: float | None) -> float:
    symbol_upper = symbol.upper()
    if symbol_upper.startswith("BTC") or symbol_upper.startswith("ETH"):
        return 10.0

    if quote_volume is not None and quote_volume < 20_000_000:
        return 3.0
    if spread_pct is not None and spread_pct > 0.002:
        return 3.0

    return 5.0


def recommend_leverage_cap(
    symbol: str,
    entry_price: float,
    sl_price: float,
    atr_15m: float,
    regime: str,
    spread_pct: float | None = None,
    quote_volume: float | None = None,
    safety_factor: float = 2.0,
) -> dict:
    if entry_price <= 0 or sl_price <= 0:
        return {
            "sl_distance_pct": 0.0,
            "atr_15m": atr_15m,
            "atr_pct": 0.0,
            "recommended_leverage_cap": 1.0,
            "recommended_leverage_cap_reason": "invalid prices",
        }

    sl_distance_pct = abs(entry_price - sl_price) / entry_price
    atr_pct = atr_15m / entry_price if entry_price > 0 else 0.0

    reasons: list[str] = []
    if sl_distance_pct <= 0:
        base_cap = 1.0
        reasons.append("zero sl distance")
    else:
        base_cap = 1 / (sl_distance_pct * safety_factor)
        reasons.append(f"base=1/(sl_pct*{safety_factor:.1f})")

    cap = base_cap

    if atr_15m > 0 and sl_distance_pct < atr_pct:
        cap *= 0.7
        reasons.append("atr guard")

    if regime == "RANGE":
        cap *= 0.7
        reasons.append("range guard")

    if spread_pct is not None and spread_pct > 0.0015:
        cap *= 0.8
        reasons.append("spread guard")

    if quote_volume is not None and quote_volume < 10_000_000:
        cap *= 0.8
        reasons.append("liquidity guard")

    cap_max = _asset_class_cap(symbol, quote_volume, spread_pct)
    cap = clamp(cap, 1.0, cap_max)
    cap = _round_down_to_allowed(cap)
    cap = clamp(cap, 1.0, cap_max)

    return {
        "sl_distance_pct": sl_distance_pct,
        "atr_15m": atr_15m,
        "atr_pct": atr_pct,
        "recommended_leverage_cap": cap,
        "recommended_leverage_cap_reason": ", ".join(reasons),
    }

