import math


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def log1p(value: float) -> float:
    return math.log1p(max(value, 0.0))

