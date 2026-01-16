from __future__ import annotations

from typing import Any

import pandas as pd

from core.features.indicators import atr, ema
from core.features.swing import recent_swing_high, recent_swing_low
from core.utils.math import safe_div

PRICE_CHANGE_LOOKBACK = 3
PRICE_STALL_PCT = 0.001
SQUEEZE_LOOKBACK = 20
VOLUME_LOOKBACK = 20
VOLUME_SPIKE_MULT = 1.5


def _float_from_keys(data: dict, keys: list[str]) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _int_from_keys(data: dict, keys: list[str]) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def extract_funding_rate(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    if isinstance(raw, list):
        if not raw:
            return None
        last = raw[-1]
        if isinstance(last, dict):
            return _float_from_keys(last, ["fundingRate", "fundingRateValue"])
        if isinstance(last, (int, float)):
            return float(last)
        return None
    if isinstance(raw, dict):
        return _float_from_keys(raw, ["fundingRate", "fundingRateValue"])
    return None


def extract_open_interest_series(raw: Any) -> list[tuple[int | None, float]]:
    series: list[tuple[int | None, float]] = []
    if raw is None:
        return series
    items: list[Any]
    default_ts = None
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        default_ts = _int_from_keys(raw, ["ts", "timestamp", "time", "openInterestTime"])
        if isinstance(raw.get("openInterestList"), list):
            items = raw["openInterestList"]
        else:
            items = [raw]
    else:
        return series

    for item in items:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                ts = int(float(item[0]))
            except (TypeError, ValueError):
                ts = None
            try:
                value = float(item[1])
            except (TypeError, ValueError):
                continue
            series.append((ts, value))
            continue
        if not isinstance(item, dict):
            continue
        value = _float_from_keys(
            item,
            ["openInterest", "openInterestAmount", "oi", "open_interest", "size"],
        )
        if value is None:
            continue
        ts = _int_from_keys(item, ["ts", "timestamp", "time", "openInterestTime"]) or default_ts
        series.append((ts, value))

    series.sort(key=lambda pair: pair[0] or 0)
    return series


def compute_oi_change_pct(series: list[tuple[int | None, float]]) -> float | None:
    if len(series) < 2:
        return None
    _, last_value = series[-1]
    _, prev_value = series[-2]
    if prev_value == 0:
        return None
    return safe_div(last_value - prev_value, prev_value)


def compute_price_change_pct(candles: pd.DataFrame, lookback: int = PRICE_CHANGE_LOOKBACK) -> float:
    if candles is None or candles.empty:
        return 0.0
    if len(candles) < 2:
        return 0.0
    if len(candles) <= lookback:
        lookback = len(candles) - 1
    last_close = float(candles["close"].iloc[-1])
    prev_close = float(candles["close"].iloc[-1 - lookback])
    return safe_div(last_close - prev_close, prev_close)


def compute_extension_pct(candles: pd.DataFrame, ema_span: int = 20) -> float | None:
    if candles is None or candles.empty or len(candles) < ema_span:
        return None
    last_close = float(candles["close"].iloc[-1])
    ema_val = float(ema(candles["close"], ema_span).iloc[-1])
    if ema_val == 0:
        return None
    return abs(last_close - ema_val) / ema_val


def detect_squeeze(
    candles: pd.DataFrame, atr_period: int, lookback: int, threshold: float
) -> bool:
    if candles is None or candles.empty:
        return False
    atr_series = atr(candles, atr_period).dropna()
    if atr_series.empty or len(atr_series) < lookback:
        return False
    atr_last = float(atr_series.iloc[-1])
    atr_mean = float(atr_series.tail(lookback).mean())
    if atr_mean == 0:
        return False
    return (atr_last / atr_mean) <= threshold


def detect_breakout_direction(candles: pd.DataFrame, lookback: int) -> str | None:
    if candles is None or candles.empty:
        return None
    last_close = float(candles["close"].iloc[-1])
    recent_high = recent_swing_high(candles, lookback)
    recent_low = recent_swing_low(candles, lookback)
    if last_close > recent_high:
        return "LONG"
    if last_close < recent_low:
        return "SHORT"
    return None


def detect_volume_expansion(candles: pd.DataFrame, lookback: int, mult: float) -> bool:
    if candles is None or candles.empty:
        return False
    volume = candles["volume"]
    if len(volume) < lookback:
        avg = float(volume.mean()) if not volume.empty else 0.0
    else:
        avg = float(volume.tail(lookback).mean())
    last = float(volume.iloc[-1])
    return avg > 0 and last > avg * mult


def analyze_market_conditions(
    direction: str,
    candles_trigger: pd.DataFrame,
    funding_rate: float | None,
    oi_change_pct: float | None,
    settings,
    market_context: dict | None = None,
) -> dict:
    risk_flags: list[str] = []

    crowded_long = (
        funding_rate is not None and funding_rate >= settings.funding_extreme_threshold
    )
    crowded_short = (
        funding_rate is not None and funding_rate <= -settings.funding_extreme_threshold
    )
    if crowded_long:
        risk_flags.append("crowded_long")
    if crowded_short:
        risk_flags.append("crowded_short")

    price_change_pct = compute_price_change_pct(candles_trigger)
    oi_confirm = False
    oi_divergence = False
    if oi_change_pct is not None and oi_change_pct >= settings.min_oi_change_pct:
        if direction == "LONG" and price_change_pct > 0:
            oi_confirm = True
        elif direction == "SHORT" and price_change_pct < 0:
            oi_confirm = True

        if abs(price_change_pct) <= PRICE_STALL_PCT:
            oi_divergence = True
        elif direction == "LONG" and price_change_pct < 0:
            oi_divergence = True
        elif direction == "SHORT" and price_change_pct > 0:
            oi_divergence = True

    if oi_divergence:
        risk_flags.append("oi_divergence")

    extension_pct = compute_extension_pct(candles_trigger)
    overextended = (
        extension_pct is not None and extension_pct > settings.max_extension_pct
    )
    if overextended:
        risk_flags.append("overextended")

    thin_liquidity = False
    if market_context:
        spread = market_context.get("spread")
        quote_volume = market_context.get("quote_volume")
        if spread is not None and spread >= settings.max_spread * 0.9:
            thin_liquidity = True
        if quote_volume is not None and quote_volume <= settings.min_quote_volume * 1.1:
            thin_liquidity = True
    if thin_liquidity:
        risk_flags.append("thin_liquidity")

    late_move = False
    if candles_trigger is not None and not candles_trigger.empty:
        atr_series = atr(candles_trigger, settings.atr_period).dropna()
        if not atr_series.empty:
            atr_value = float(atr_series.iloc[-1])
            lookback = min(settings.swing_lookback, len(candles_trigger))
            recent_range = float(
                candles_trigger["high"].tail(lookback).max()
                - candles_trigger["low"].tail(lookback).min()
            )
            if atr_value > 0 and recent_range / atr_value >= settings.late_move_atr_mult:
                late_move = True
    if late_move:
        risk_flags.append("late_move")

    squeeze_ready = detect_squeeze(
        candles_trigger, settings.atr_period, SQUEEZE_LOOKBACK, settings.squeeze_threshold
    )
    breakout_direction = detect_breakout_direction(
        candles_trigger, settings.swing_lookback
    )
    volume_expansion = detect_volume_expansion(
        candles_trigger, VOLUME_LOOKBACK, VOLUME_SPIKE_MULT
    )
    early_ready = (
        squeeze_ready
        and breakout_direction == direction
        and volume_expansion
        and oi_confirm
    )

    return {
        "risk_flags": risk_flags,
        "oi_confirm": oi_confirm,
        "oi_divergence": oi_divergence,
        "overextended": overextended,
        "extension_pct": extension_pct,
        "crowded_long": crowded_long,
        "crowded_short": crowded_short,
        "thin_liquidity": thin_liquidity,
        "late_move": late_move,
        "squeeze_ready": squeeze_ready,
        "breakout_direction": breakout_direction,
        "volume_expansion": volume_expansion,
        "early_pump_dump_ready": early_ready,
        "price_change_pct": price_change_pct,
    }
