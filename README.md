# Bitget Futures Public Signal Scanner

Local scanner that ranks USDT perpetual pairs and produces manual trade signals
with entry, SL, and TP levels. Data is pulled from Bitget public endpoints.

## Quick start

1. Create a virtual environment.
2. Install deps:
   `pip install -r requirements.txt`
3. Run the dashboard:
   `streamlit run app/main.py`

Optional CLI scan:
`python scripts/run_scan.py`

