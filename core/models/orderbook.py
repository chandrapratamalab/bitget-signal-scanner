from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderBookSnapshot:
    symbol: str
    bids: list[list[float]]
    asks: list[list[float]]
    ts_ms: int
    source: str
    seq: int | None = None
