import os


BASE_URL = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
PRODUCT_TYPE = os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES")

ENDPOINTS = {
    "contracts": "/api/v2/mix/market/contracts",
    "tickers": "/api/v2/mix/market/tickers",
    "candles": "/api/v2/mix/market/candles",
}

GRANULARITY_SECONDS = {
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}

