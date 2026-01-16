from __future__ import annotations

from typing import Iterable

from core.config.constants import GRANULARITY_SECONDS
from core.config.settings import SCAN_MODE_SCALP, Settings, resolve_timeframes
from core.data.bitget_client import BitgetClient
from core.scanner.stage1_rank import rank_stage1
from core.scanner.stage2_score import score_stage2
from core.signals.generator import generate_signal
from core.signals.market_filters import (
    compute_oi_change_pct,
    extract_funding_rate,
    extract_open_interest_series,
)
from core.utils.cache import load_oi_snapshot, save_oi_snapshot
from core.utils.io import save_signals_csv
from core.utils.math import safe_div


def _float_from_keys(data: dict, keys: Iterable[str], default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _string_from_keys(data: dict, keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return default


def _build_universe(contracts: list[dict]) -> set[str]:
    symbols: set[str] = set()
    for contract in contracts:
        symbol = _string_from_keys(contract, ["symbol", "symbolName", "instrumentId"])
        if not symbol:
            continue
        status = str(
            _string_from_keys(
                contract, ["status", "symbolStatus", "state", "trading"]
            )
        ).lower()
        if status and status not in ("normal", "online", "1", "true"):
            continue
        symbols.add(symbol.upper())
    return symbols


def _normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in symbols:
        symbol = (raw or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _stage1_notes(
    quote_volume: float, spread: float, move_24h: float, settings: Settings
) -> list[str]:
    notes: list[str] = []
    if quote_volume < settings.min_quote_volume:
        notes.append("min_quote_volume")
    if spread > settings.max_spread:
        notes.append("max_spread")
    if move_24h < settings.min_move_24h:
        notes.append("min_move_24h")
    return notes


def run_scan(
    client: BitgetClient,
    settings: Settings,
    output_path: str = "data/outputs/signals.csv",
) -> dict:
    oi_snapshot = load_oi_snapshot()
    contracts = client.get_contracts(settings.product_type)
    tickers = client.get_tickers(settings.product_type)

    stage1 = rank_stage1(contracts, tickers, settings)
    stage2_raw, candles_cache = score_stage2(
        client, stage1, settings, limit=settings.top_k
    )
    timeframes = resolve_timeframes(settings)
    bias_tf = timeframes["bias_tf"]
    confirm_tf = timeframes["confirm_tf"]
    trigger_tf = timeframes["trigger_tf"]
    stage1_map = {item["symbol"]: item for item in stage1}
    stage2: list[dict] = []
    for item in stage2_raw:
        stage1_item = stage1_map.get(item["symbol"], {})
        merged = {
            **item,
            "quote_volume": stage1_item.get("quote_volume"),
            "spread": stage1_item.get("spread"),
            "move_24h": stage1_item.get("move_24h"),
        }
        stage2.append(merged)

    signals: list[dict] = []
    for item in stage2:
        symbol = item["symbol"]
        candles_bias = candles_cache.get(bias_tf, {}).get(symbol)
        candles_confirm = candles_cache.get(confirm_tf, {}).get(symbol)
        if confirm_tf == bias_tf:
            candles_confirm = candles_bias
        candles_trigger = client.get_candles(
            symbol,
            GRANULARITY_SECONDS[trigger_tf],
            settings.candles_limit,
            settings.product_type,
        )
        candles_by_tf = {
            bias_tf: candles_bias,
            confirm_tf: candles_confirm,
            trigger_tf: candles_trigger,
        }

        funding_rate = None
        open_interest = None
        oi_change_pct = None
        needs_funding_oi = settings.show_funding_oi or settings.strict_filters or (
            timeframes["scan_mode"] == SCAN_MODE_SCALP
        )
        oi_series: list[tuple[int | None, float]] = []
        if needs_funding_oi:
            try:
                funding_rate = extract_funding_rate(
                    client.get_current_funding_rate(symbol, settings.product_type)
                )
                oi_series = extract_open_interest_series(
                    client.get_open_interest(symbol, settings.product_type)
                )
                if oi_series:
                    open_interest = oi_series[-1][1]
                oi_change_pct = compute_oi_change_pct(oi_series)
                if oi_change_pct is None and open_interest is not None:
                    prev_entry = oi_snapshot.get(symbol)
                    prev_value = None
                    if isinstance(prev_entry, dict):
                        prev_value = prev_entry.get("value")
                    elif isinstance(prev_entry, (int, float)):
                        prev_value = float(prev_entry)
                    if prev_value:
                        oi_change_pct = (open_interest - prev_value) / prev_value
            except Exception:  # noqa: BLE001
                funding_rate = None
                open_interest = None
                oi_change_pct = None
                oi_series = []
        if open_interest is not None:
            last_ts = oi_series[-1][0] if oi_series else None
            oi_snapshot[symbol] = {"value": open_interest, "ts": last_ts}
        signal = generate_signal(
            symbol,
            candles_by_tf,
            settings,
            market_context=item,
            funding_rate=funding_rate,
            open_interest=open_interest,
            oi_change_pct=oi_change_pct,
        )
        if signal:
            signals.append(signal)

    save_oi_snapshot(oi_snapshot)
    save_signals_csv(signals, output_path)
    return {"stage1": stage1, "stage2": stage2, "signals": signals}


def run_custom_scan(
    client: BitgetClient,
    settings: Settings,
    symbols: list[str],
    output_path: str | None = "data/outputs/custom_signals.csv",
) -> dict:
    normalized = _normalize_symbols(symbols)
    if not normalized:
        return {"symbols": [], "stage1": [], "stage2": [], "signals": [], "skipped": []}

    oi_snapshot = load_oi_snapshot()
    contracts = client.get_contracts(settings.product_type)
    tickers = client.get_tickers(settings.product_type)
    universe = _build_universe(contracts) if contracts else set()

    ticker_map: dict[str, dict] = {}
    for ticker in tickers:
        symbol = _string_from_keys(ticker, ["symbol", "instrumentId"])
        if not symbol:
            continue
        ticker_map[symbol.upper()] = ticker

    stage1: list[dict] = []
    candidates: list[dict] = []
    skipped: list[dict] = []
    for symbol in normalized:
        if universe and symbol not in universe:
            skipped.append({"symbol": symbol, "reason": "not_in_contracts"})
            continue
        ticker = ticker_map.get(symbol)
        if ticker is None:
            skipped.append({"symbol": symbol, "reason": "ticker_not_found"})
            continue

        last = _float_from_keys(ticker, ["lastPr", "last", "lastPrice"])
        bid = _float_from_keys(ticker, ["bidPr", "bid", "bestBid"])
        ask = _float_from_keys(ticker, ["askPr", "ask", "bestAsk"])
        quote_volume = _float_from_keys(
            ticker, ["quoteVolume", "quoteVol", "usdtVolume", "quoteVol24h"]
        )
        change_24h = _float_from_keys(
            ticker, ["change24h", "priceChangePercent", "chg24h"]
        )
        spread = safe_div(ask - bid, last)
        move_24h = abs(change_24h)

        notes = _stage1_notes(quote_volume, spread, move_24h, settings)
        stage1.append(
            {
                "symbol": symbol,
                "quote_volume": quote_volume,
                "spread": spread,
                "move_24h": move_24h,
                "stage1_ok": not notes,
                "stage1_notes": ", ".join(notes),
            }
        )
        candidates.append({"symbol": symbol})

    if not candidates:
        return {
            "symbols": normalized,
            "stage1": stage1,
            "stage2": [],
            "signals": [],
            "skipped": skipped,
        }

    stage2_raw, candles_cache = score_stage2(client, candidates, settings, limit=None)
    stage2_symbols = {item["symbol"] for item in stage2_raw}
    for item in stage1:
        if item["symbol"] not in stage2_symbols:
            skipped.append({"symbol": item["symbol"], "reason": "insufficient_candles"})

    stage1_map = {item["symbol"]: item for item in stage1}
    stage2: list[dict] = []
    for item in stage2_raw:
        stage1_item = stage1_map.get(item["symbol"], {})
        stage2.append({**item, **stage1_item})

    timeframes = resolve_timeframes(settings)
    bias_tf = timeframes["bias_tf"]
    confirm_tf = timeframes["confirm_tf"]
    trigger_tf = timeframes["trigger_tf"]
    signals: list[dict] = []
    for item in stage2:
        symbol = item["symbol"]
        candles_bias = candles_cache.get(bias_tf, {}).get(symbol)
        candles_confirm = candles_cache.get(confirm_tf, {}).get(symbol)
        if confirm_tf == bias_tf:
            candles_confirm = candles_bias
        candles_trigger = client.get_candles(
            symbol,
            GRANULARITY_SECONDS[trigger_tf],
            settings.candles_limit,
            settings.product_type,
        )
        candles_by_tf = {
            bias_tf: candles_bias,
            confirm_tf: candles_confirm,
            trigger_tf: candles_trigger,
        }

        funding_rate = None
        open_interest = None
        oi_change_pct = None
        needs_funding_oi = settings.show_funding_oi or settings.strict_filters or (
            timeframes["scan_mode"] == SCAN_MODE_SCALP
        )
        oi_series: list[tuple[int | None, float]] = []
        if needs_funding_oi:
            try:
                funding_rate = extract_funding_rate(
                    client.get_current_funding_rate(symbol, settings.product_type)
                )
                oi_series = extract_open_interest_series(
                    client.get_open_interest(symbol, settings.product_type)
                )
                if oi_series:
                    open_interest = oi_series[-1][1]
                oi_change_pct = compute_oi_change_pct(oi_series)
                if oi_change_pct is None and open_interest is not None:
                    prev_entry = oi_snapshot.get(symbol)
                    prev_value = None
                    if isinstance(prev_entry, dict):
                        prev_value = prev_entry.get("value")
                    elif isinstance(prev_entry, (int, float)):
                        prev_value = float(prev_entry)
                    if prev_value:
                        oi_change_pct = (open_interest - prev_value) / prev_value
            except Exception:  # noqa: BLE001
                funding_rate = None
                open_interest = None
                oi_change_pct = None
                oi_series = []
        if open_interest is not None:
            last_ts = oi_series[-1][0] if oi_series else None
            oi_snapshot[symbol] = {"value": open_interest, "ts": last_ts}
        signal = generate_signal(
            symbol,
            candles_by_tf,
            settings,
            market_context=item,
            funding_rate=funding_rate,
            open_interest=open_interest,
            oi_change_pct=oi_change_pct,
        )
        if signal:
            signals.append(signal)

    save_oi_snapshot(oi_snapshot)
    if output_path:
        save_signals_csv(signals, output_path)
    return {
        "symbols": normalized,
        "stage1": stage1,
        "stage2": stage2,
        "signals": signals,
        "skipped": skipped,
    }
