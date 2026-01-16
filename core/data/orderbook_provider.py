from __future__ import annotations

import time
from typing import Any

from core.config.constants import WS_PUBLIC_URL
from core.data.bitget_client import BitgetClient
from core.data.bitget_ws_client import BitgetWSClient
from core.models.orderbook import OrderBookSnapshot


def _parse_side(entries: Any) -> list[list[float]]:
    parsed: list[list[float]] = []
    if not isinstance(entries, list):
        return parsed
    for item in entries:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            price = float(item[0])
            size = float(item[1])
        except (TypeError, ValueError):
            continue
        parsed.append([price, size])
    return parsed


def _parse_ts_ms(value: Any) -> int:
    if value is None:
        return int(time.time() * 1000)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(time.time() * 1000)


def _extract_book(raw: Any) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        if "data" in raw and isinstance(raw["data"], dict):
            return raw["data"]
        if "data" in raw and isinstance(raw["data"], list) and raw["data"]:
            return raw["data"][0]
        return raw
    if isinstance(raw, list) and raw:
        if isinstance(raw[0], dict):
            return raw[0]
    return None


class OrderbookProvider:
    def __init__(
        self,
        rest_client: BitgetClient,
        enable_ws: bool = False,
        channel: str = "books5",
        inst_type: str = "USDT-FUTURES",
        reconnect_backoff_ms: int = 1500,
        stale_timeout_sec: int = 3,
        fallback_to_rest: bool = True,
    ) -> None:
        self.rest_client = rest_client
        self.enable_ws = enable_ws
        self.channel = channel
        self.inst_type = inst_type
        self.reconnect_backoff_ms = reconnect_backoff_ms
        self.stale_timeout_sec = stale_timeout_sec
        self.fallback_to_rest = fallback_to_rest
        self._ws_client: BitgetWSClient | None = None

        if self.enable_ws:
            self._ws_client = BitgetWSClient(
                WS_PUBLIC_URL,
                inst_type=self.inst_type,
                channel=self.channel,
                reconnect_backoff_ms=self.reconnect_backoff_ms,
            )

    def update_settings(
        self,
        enable_ws: bool,
        channel: str,
        inst_type: str,
        reconnect_backoff_ms: int,
        stale_timeout_sec: int,
        fallback_to_rest: bool,
    ) -> None:
        config_changed = (
            enable_ws != self.enable_ws
            or channel != self.channel
            or inst_type != self.inst_type
            or reconnect_backoff_ms != self.reconnect_backoff_ms
        )
        self.enable_ws = enable_ws
        self.channel = channel
        self.inst_type = inst_type
        self.reconnect_backoff_ms = reconnect_backoff_ms
        self.stale_timeout_sec = stale_timeout_sec
        self.fallback_to_rest = fallback_to_rest

        if config_changed:
            if self._ws_client is not None:
                self._ws_client.close()
                self._ws_client = None
            if self.enable_ws:
                self._ws_client = BitgetWSClient(
                    WS_PUBLIC_URL,
                    inst_type=self.inst_type,
                    channel=self.channel,
                    reconnect_backoff_ms=self.reconnect_backoff_ms,
                )

    def close(self) -> None:
        if self._ws_client is not None:
            self._ws_client.close()
        self.rest_client.close()

    def get_orderbook(self, symbol: str) -> tuple[OrderBookSnapshot | None, str]:
        symbol = (symbol or "").strip().upper()
        if not symbol or symbol.lower() == "default":
            return None, "INVALID SYMBOL"

        if self.enable_ws:
            self._ensure_ws()
            if self._ws_client is not None:
                self._ws_client.subscribe_depth(symbol)
                snapshot = self._ws_client.get_snapshot(symbol)
                if snapshot and not self._ws_client.is_stale(
                    snapshot, self.stale_timeout_sec
                ):
                    return snapshot, "CONNECTED"
                if snapshot:
                    self._reconnect_ws()
                    status = "STALE"
                else:
                    status = "RECONNECTING"
                if self.fallback_to_rest:
                    rest_snapshot = self._get_rest_snapshot(symbol)
                    if rest_snapshot:
                        return rest_snapshot, "FALLBACK REST"
                return snapshot, status

        if self.fallback_to_rest:
            rest_snapshot = self._get_rest_snapshot(symbol)
            if rest_snapshot:
                return rest_snapshot, "FALLBACK REST"
        return None, "DISABLED"

    def get_health(self) -> dict[str, Any]:
        if self._ws_client is None:
            return {
                "connected": False,
                "last_pong_age": None,
                "last_message_age": None,
                "last_error": None,
                "last_connect_ts": None,
                "reconnect_count": 0,
            }
        return self._ws_client.get_health()

    def _ensure_ws(self) -> None:
        if self._ws_client is None:
            self._ws_client = BitgetWSClient(
                WS_PUBLIC_URL,
                inst_type=self.inst_type,
                channel=self.channel,
                reconnect_backoff_ms=self.reconnect_backoff_ms,
            )
        self._ws_client.connect()

    def _reconnect_ws(self) -> None:
        if self._ws_client is None:
            return
        self._ws_client.close()
        self._ws_client.connect()

    def _get_rest_snapshot(self, symbol: str) -> OrderBookSnapshot | None:
        try:
            raw = self.rest_client.get_merge_depth(symbol, self.inst_type, limit=5)
        except Exception:  # noqa: BLE001
            return None
        book = _extract_book(raw)
        if not book:
            return None
        bids = _parse_side(book.get("bids"))
        asks = _parse_side(book.get("asks"))
        if not bids and not asks:
            return None
        ts_ms = _parse_ts_ms(book.get("ts"))
        return OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            ts_ms=ts_ms,
            source="rest",
            seq=None,
        )
