from pathlib import Path

import pandas as pd


def save_signals_csv(signals: list[dict], output_path: str) -> None:
    if not signals:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(signals)
    df.to_csv(path, index=False)

