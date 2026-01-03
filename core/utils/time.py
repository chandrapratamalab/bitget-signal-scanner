from datetime import datetime, timezone

import pandas as pd

WIB_OFFSET_HOURS = 7
WIB_OFFSET_MINUTES = 420
WIB_OFFSET_LABEL = "+07:00"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_datetime_ms(value) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    return pd.to_datetime(int(value), unit="ms", utc=True)


def to_wib_string(value) -> str | None:
    if value is None or value is pd.NaT:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    local = ts + pd.Timedelta(hours=WIB_OFFSET_HOURS)
    return f"{local.strftime('%Y-%m-%d %H:%M:%S')} {WIB_OFFSET_LABEL}"
