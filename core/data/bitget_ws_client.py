from __future__ import annotations

import json
import threading
import time
from typing import Any

import websocket

from core.models.orderbook import OrderBookSnapshot

PING_INTERVAL_SEC = 30


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


class BitgetWSClient:
    def __init__(
        self,
        url: str,
        inst_type: str,
        channel: str,
        reconnect_backoff_ms: int = 1500,
    ) -> None:
        self.url = url
        self.inst_type = inst_type
        self.channel = channel
        self.reconnect_backoff_ms = reconnect_backoff_ms

        self._ws_app: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._ping_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._snapshots: dict[str, OrderBookSnapshot] = {}
        self._subscribed_symbols: set[str] = set()

        self.last_error: str | None = None
        self.last_pong_ts: float | None = None
        self.last_message_ts: float | None = None
        self.last_connect_ts: float | None = None
        self.reconnect_count: int = 0
        self._ever_connected = False
        self._last_connect_attempt: float = 0.0

    def connect(self) -> None:
        with self._lock:
            if self._ws_thread and self._ws_thread.is_alive():
                if self.is_connected():
                    return
                try:
                    if self._ws_app is not None:
                        self._ws_app.close()
                except Exception:  # noqa: BLE001
                    pass
                self._ws_thread.join(timeout=1.0)
            now = time.time()
            if now - self._last_connect_attempt < self.reconnect_backoff_ms / 1000.0:
                return
            self._last_connect_attempt = now
            self._stop_event.clear()
            self._ws_app = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self._ws_thread = threading.Thread(
                target=self._ws_app.run_forever,
                kwargs={"ping_interval": None},
                daemon=True,
            )
            self._ws_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        if self._ws_app is not None:
            try:
                self._ws_app.close()
            except Exception:  # noqa: BLE001
                pass
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=1.0)
        self._ws_thread = None
        if self._ping_thread and self._ping_thread.is_alive():
            self._ping_thread.join(timeout=1.0)
        self._ping_thread = None

    def subscribe_depth(self, symbol: str) -> None:
        self._subscribed_symbols.add(symbol)
        if self.is_connected():
            self._send_subscribe(symbol)

    def is_connected(self) -> bool:
        return bool(self._ws_app and self._ws_app.sock and self._ws_app.sock.connected)

    def get_snapshot(self, symbol: str) -> OrderBookSnapshot | None:
        with self._lock:
            return self._snapshots.get(symbol)

    def is_stale(self, snapshot: OrderBookSnapshot, stale_timeout_sec: int) -> bool:
        now_ms = int(time.time() * 1000)
        return (now_ms - snapshot.ts_ms) > int(stale_timeout_sec * 1000)

    def get_health(self) -> dict[str, Any]:
        now = time.time()
        pong_age = None
        msg_age = None
        if self.last_pong_ts is not None:
            pong_age = now - self.last_pong_ts
        if self.last_message_ts is not None:
            msg_age = now - self.last_message_ts
        return {
            "connected": self.is_connected(),
            "last_pong_age": pong_age,
            "last_message_age": msg_age,
            "last_error": self.last_error,
            "last_connect_ts": self.last_connect_ts,
            "reconnect_count": self.reconnect_count,
        }

    def _start_ping_loop(self) -> None:
        if self._ping_thread and self._ping_thread.is_alive():
            return
        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

    def _ping_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.is_connected() and self._ws_app is not None:
                try:
                    self._ws_app.send("ping")
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(PING_INTERVAL_SEC)

    def _send_subscribe(self, symbol: str) -> None:
        if self._ws_app is None:
            return
        payload = {
            "op": "subscribe",
            "args": [
                {
                    "instType": self.inst_type,
                    "channel": self.channel,
                    "instId": symbol,
                }
            ],
        }
        try:
            self._ws_app.send(json.dumps(payload))
        except Exception:  # noqa: BLE001
            self.last_error = "subscribe_failed"

    def _on_open(self, ws) -> None:  # noqa: ANN001
        self.last_error = None
        if self._ever_connected:
            self.reconnect_count += 1
        else:
            self._ever_connected = True
        self.last_connect_ts = time.time()
        self._start_ping_loop()
        for symbol in list(self._subscribed_symbols):
            self._send_subscribe(symbol)

    def _on_message(self, ws, message: str) -> None:  # noqa: ANN001
        if message == "pong":
            self.last_pong_ts = time.time()
            return

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return

        if isinstance(payload, dict) and payload.get("event") == "error":
            self.last_error = payload.get("msg") or "ws_error"
            return

        if not isinstance(payload, dict):
            return

        action = payload.get("action")
        if action not in ("snapshot", "update"):
            return

        arg = payload.get("arg") or {}
        symbol = arg.get("instId") or arg.get("symbol")
        if not symbol:
            return

        data = payload.get("data")
        book = None
        if isinstance(data, list) and data:
            book = data[0]
        elif isinstance(data, dict):
            book = data
        if not isinstance(book, dict):
            return

        bids = _parse_side(book.get("bids"))
        asks = _parse_side(book.get("asks"))
        ts_ms = _parse_ts_ms(book.get("ts") or payload.get("ts"))
        seq = None
        try:
            if "seq" in book:
                seq = int(book.get("seq"))
        except (TypeError, ValueError):
            seq = None

        snapshot = OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            ts_ms=ts_ms,
            source="ws",
            seq=seq,
        )
        with self._lock:
            self._snapshots[symbol] = snapshot
            self.last_message_ts = time.time()

    def _on_error(self, ws, error) -> None:  # noqa: ANN001
        self.last_error = str(error)

    def _on_close(self, ws, close_status_code, close_msg) -> None:  # noqa: ANN001
        self.last_error = close_msg or "ws_closed"
