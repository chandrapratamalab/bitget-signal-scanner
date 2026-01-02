from __future__ import annotations

from core.config.constants import GRANULARITY_SECONDS
from core.config.settings import Settings
from core.data.bitget_client import BitgetClient
from core.scanner.stage1_rank import rank_stage1
from core.scanner.stage2_score import score_stage2
from core.signals.generator import generate_signal
from core.utils.io import save_signals_csv


def run_scan(
    client: BitgetClient,
    settings: Settings,
    output_path: str = "data/outputs/signals.csv",
) -> dict:
    contracts = client.get_contracts(settings.product_type)
    tickers = client.get_tickers(settings.product_type)

    stage1 = rank_stage1(contracts, tickers, settings)
    stage2, candles_4h_cache = score_stage2(client, stage1, settings)

    signals: list[dict] = []
    for item in stage2:
        symbol = item["symbol"]
        candles_4h = candles_4h_cache.get(symbol)
        candles_15m = client.get_candles(
            symbol,
            GRANULARITY_SECONDS["15m"],
            settings.candles_limit,
            settings.product_type,
        )
        signal = generate_signal(symbol, candles_4h, candles_15m, settings)
        if signal:
            signals.append(signal)

    save_signals_csv(signals, output_path)
    return {"stage1": stage1, "stage2": stage2, "signals": signals}

