import os


BASE_URL = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
WS_PUBLIC_URL = os.getenv("BITGET_WS_PUBLIC_URL", "wss://ws.bitget.com/v2/ws/public")
PRODUCT_TYPE = os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES")

ENDPOINTS = {
    "contracts": "/api/v2/mix/market/contracts",
    "tickers": "/api/v2/mix/market/tickers",
    "candles": "/api/v2/mix/market/candles",
    "merge_depth": "/api/v2/mix/market/merge-depth",
    "open_interest": "/api/v2/mix/market/open-interest",
    "current_fund_rate": "/api/v2/mix/market/current-fund-rate",
    "history_fund_rate": "/api/v2/mix/market/history-fund-rate",
}

GRANULARITY_SECONDS = {
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
}
