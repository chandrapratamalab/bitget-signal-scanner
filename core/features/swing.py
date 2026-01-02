import pandas as pd


def recent_swing_high(df: pd.DataFrame, lookback: int) -> float:
    if df.empty:
        return 0.0
    return float(df["high"].tail(lookback).max())


def recent_swing_low(df: pd.DataFrame, lookback: int) -> float:
    if df.empty:
        return 0.0
    return float(df["low"].tail(lookback).min())

