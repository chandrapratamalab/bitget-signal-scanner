from dataclasses import dataclass

from core.config.constants import PRODUCT_TYPE


@dataclass
class Settings:
    product_type: str = PRODUCT_TYPE
    top_n_candidates: int = 50
    top_k: int = 5
    candles_limit: int = 240

    min_quote_volume: float = 5_000_000.0
    max_spread: float = 0.0015
    min_move_24h: float = 0.0

    stage1_weight_volume: float = 1.0
    stage1_weight_spread: float = 2.0
    stage1_weight_move: float = 0.5

    stage2_weight_trend: float = 1.0
    stage2_weight_slope: float = 0.5
    stage2_weight_efficiency: float = 0.2

    atr_period: int = 14
    atr_mult: float = 1.2
    swing_lookback: int = 20
    slope_lookback: int = 10
    entry_buffer_pct: float = 0.001


def default_settings() -> Settings:
    return Settings()

