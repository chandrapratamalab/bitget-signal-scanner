# Bitget Futures Public Signal Scanner V 1.0

Local scanner that ranks USDT perpetual pairs and produces manual trade signals
with entry, SL, and TP levels. Data is pulled from Bitget public endpoints.

## Model

This project does not use a machine learning model. Signals are generated with
rule-based technical analysis (EMA trend regime, break+retest entry, ATR/swing
stop loss, and R-multiple take profits).

**Author:** Chandra Pratama

## Overview

This project is designed for **personal use** to help identify which Bitget **USDT perpetual futures** pairs are most “tradeable” at a given time, then generate a **manual trade plan**:

- Direction (LONG/SHORT)
- Entry plan (e.g., break & retest)
- Stop Loss (SL)
- Take Profit targets (TP1/TP2)
- Invalidation condition (when the setup is considered failed)

It uses **public market data only** (no API key, no account access).

## Learning / Model Approach

This version uses a **rule-based scoring model** (deterministic, not machine learning) to:

1. **Rank pairs** using market metrics such as liquidity, spread proxy, volatility, and trend clarity.
2. **Generate signals** using multi-timeframe technical rules:
   - **4H**: market regime (trend/range) and directional bias
   - **1H**: setup validation (structure / pullback context)
   - **15m**: entry trigger (break + retest), then SL/TP calculation

> Note: The term “model” here refers to a **scoring + rules engine**, not a trained ML model.
> A future upgrade (v2/v3) can add a supervised ML model, such as **XGBoost/LightGBM**,
> to estimate probabilities (e.g., `P(TP_first)` using triple-barrier labeling) and improve filtering.

## Quick start

1. Create a virtual environment.
2. Install deps:
   `pip install -r requirements.txt`
3. Run the dashboard:
   `streamlit run app/main.py`

Optional CLI scan:
`python scripts/run_scan.py`
