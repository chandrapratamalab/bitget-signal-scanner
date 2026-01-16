from dataclasses import dataclass

from core.config.constants import GRANULARITY_SECONDS, PRODUCT_TYPE

SCAN_MODE_TREND = "TREND"
SCAN_MODE_SCALP = "SCALP"


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

    scan_mode: str = SCAN_MODE_TREND
    trend_bias_tf: str = "4h"
    trend_confirm_tf: str = "1h"
    trend_entry_tf: str = "15m"
    show_funding_oi: bool = True
    strict_trend_alignment: bool = False
    strict_filters: bool = False

    scalp_bias_tf: str = "1h"
    scalp_trigger_tf: str = "15m"
    use_funding_filter: bool = True
    use_oi_confirmation: bool = True
    use_overextension_filter: bool = True

    funding_extreme_threshold: float = 0.001
    min_oi_change_pct: float = 0.02
    max_extension_pct: float = 0.02
    squeeze_threshold: float = 0.7
    late_move_atr_mult: float = 3.0

    enable_ws_orderbook: bool = False
    ws_orderbook_channel: str = "books5"
    ws_inst_type: str = "USDT-FUTURES"
    ws_ui_refresh_ms: int = 1000
    ws_reconnect_backoff_ms: int = 1500
    ws_stale_timeout_sec: int = 10
    fallback_to_rest: bool = True


def default_settings() -> Settings:
    return Settings()


def resolve_timeframes(settings: Settings) -> dict[str, str]:
    scan_mode = settings.scan_mode.upper()
    if scan_mode == SCAN_MODE_SCALP:
        bias_tf = settings.scalp_bias_tf.lower()
        trigger_tf = settings.scalp_trigger_tf.lower()
        if bias_tf not in GRANULARITY_SECONDS:
            bias_tf = "1h"
        if trigger_tf not in GRANULARITY_SECONDS:
            trigger_tf = "15m"
        confirm_tf = bias_tf
    else:
        scan_mode = SCAN_MODE_TREND
        bias_tf = settings.trend_bias_tf.lower()
        confirm_tf = settings.trend_confirm_tf.lower()
        trigger_tf = settings.trend_entry_tf.lower()
        if bias_tf not in GRANULARITY_SECONDS:
            bias_tf = "4h"
        if confirm_tf not in GRANULARITY_SECONDS:
            confirm_tf = "1h"
        if trigger_tf not in GRANULARITY_SECONDS:
            trigger_tf = "15m"

    return {
        "scan_mode": scan_mode,
        "bias_tf": bias_tf,
        "confirm_tf": confirm_tf,
        "trigger_tf": trigger_tf,
    }
