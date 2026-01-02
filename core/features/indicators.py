import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def efficiency_ratio(series: pd.Series, period: int = 20) -> float:
    if len(series) < period + 1:
        return 0.0
    change = abs(series.iloc[-1] - series.iloc[-period - 1])
    volatility = series.diff().abs().tail(period).sum()
    if volatility == 0:
        return 0.0
    return float(change / volatility)

