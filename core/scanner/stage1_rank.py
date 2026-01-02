from __future__ import annotations

from typing import Iterable

from core.config.settings import Settings
from core.utils.math import log1p, safe_div


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
        symbols.add(symbol)
    return symbols


def rank_stage1(
    contracts: list[dict], tickers: list[dict], settings: Settings
) -> list[dict]:
    universe = _build_universe(contracts) if contracts else set()
    results: list[dict] = []

    for ticker in tickers:
        symbol = _string_from_keys(ticker, ["symbol", "instrumentId"])
        if not symbol:
            continue
        if universe and symbol not in universe:
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

        if quote_volume < settings.min_quote_volume:
            continue

        spread = safe_div(ask - bid, last)
        if spread > settings.max_spread:
            continue

        move = abs(change_24h)
        if move < settings.min_move_24h:
            continue

        score = (
            settings.stage1_weight_volume * log1p(quote_volume)
            - settings.stage1_weight_spread * spread
            + settings.stage1_weight_move * move
        )

        results.append(
            {
                "symbol": symbol,
                "score": score,
                "spread": spread,
                "quote_volume": quote_volume,
                "move_24h": move,
                "reason": f"vol={quote_volume:.0f} spread={spread:.4f} move={move:.4f}",
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: settings.top_n_candidates]

