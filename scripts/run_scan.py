import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.settings import default_settings
from core.data.bitget_client import BitgetClient
from core.scanner.pipeline import run_scan


def main() -> None:
    settings = default_settings()
    client = BitgetClient()
    try:
        results = run_scan(client, settings)
    finally:
        client.close()

    signals = results.get("signals", [])
    if not signals:
        print("No trade signals generated.")
        return

    df = pd.DataFrame(signals)[
        [
            "symbol",
            "direction",
            "entry_time",
            "entry_price",
            "sl",
            "tp1",
            "tp2",
            "recommended_leverage_cap",
        ]
    ]
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
