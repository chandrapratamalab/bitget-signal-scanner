from pathlib import Path

import pandas as pd

from core.utils.time import WIB_OFFSET_MINUTES, now_utc_iso, to_wib_string

TIME_COLUMNS = ("run_timestamp", "entry_time", "generated_at", "signal_time")
DECIMAL_4_COLUMNS = ("entry_zone_low", "entry_zone_high", "sl", "tp1", "tp2")
PERCENT_COLUMNS = ("sl_distance_pct", "atr_pct")


def _format_decimal(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _format_percent(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str) and value.endswith("%"):
        return value
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def build_signals_export_df(signals: list[dict]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame()

    run_timestamp = now_utc_iso()
    rows = []
    for signal in signals:
        row = dict(signal)
        row.setdefault("signal_time", row.get("generated_at"))
        row["run_timestamp"] = run_timestamp
        rows.append(row)

    df = pd.DataFrame(rows)
    for column in TIME_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(to_wib_string)
    for column in DECIMAL_4_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(_format_decimal)
    for column in PERCENT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(_format_percent)
    df["timezone_offset"] = "UTC+7"
    df["timezone_offset_minutes"] = WIB_OFFSET_MINUTES
    return df


def save_signals_csv(signals: list[dict], output_path: str) -> None:
    df = build_signals_export_df(signals)
    if df.empty:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
