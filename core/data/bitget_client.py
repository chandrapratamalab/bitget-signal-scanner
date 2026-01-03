from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

from core.config.constants import BASE_URL, ENDPOINTS


@dataclass
class BitgetClient:
    base_url: str = BASE_URL
    timeout: float = 10.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._client = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def _extract_data(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            code = payload.get("code")
            if code not in (None, "00000"):
                message = payload.get("msg", "unknown error")
                raise RuntimeError(f"Bitget API error {code}: {message}")
            if "data" in payload:
                return payload["data"]
            if "result" in payload:
                return payload["result"]
        return payload

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return self._extract_data(response.json())

    def get_contracts(self, product_type: str) -> list[dict]:
        params = {"productType": product_type}
        data = self._get(ENDPOINTS["contracts"], params)
        if isinstance(data, list):
            return data
        return []

    def get_tickers(self, product_type: str) -> list[dict]:
        params = {"productType": product_type}
        data = self._get(ENDPOINTS["tickers"], params)
        if isinstance(data, list):
            return data
        return []

    def get_candles(
        self, symbol: str, granularity: int, limit: int, product_type: str
    ) -> pd.DataFrame:
        params = {
            "symbol": symbol,
            "granularity": granularity,
            "limit": limit,
            "productType": product_type,
        }
        raw = self._get(ENDPOINTS["candles"], params)
        return _candles_to_df(raw)


def _candles_to_df(raw: Any) -> pd.DataFrame:
    rows: list[dict] = []
    if not raw:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    for item in raw:
        if isinstance(item, (list, tuple)):
            if len(item) >= 6:
                ts, open_, high, low, close, volume = item[:6]
            elif len(item) >= 5:
                ts, open_, high, low, close = item[:5]
                volume = 0
            else:
                continue
        elif isinstance(item, dict):
            ts = item.get("ts") or item.get("timestamp")
            open_ = item.get("open")
            high = item.get("high")
            low = item.get("low")
            close = item.get("close")
            volume = item.get("volume", 0)
        else:
            continue

        rows.append(
            {
                "ts": int(ts),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("ts").reset_index(drop=True)
    return df

