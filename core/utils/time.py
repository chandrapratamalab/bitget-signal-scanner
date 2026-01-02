from datetime import datetime, timezone

import pandas as pd


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_datetime_ms(value) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    return pd.to_datetime(int(value), unit="ms", utc=True)

