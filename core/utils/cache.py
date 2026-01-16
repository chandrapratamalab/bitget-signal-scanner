from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OI_SNAPSHOT_PATH = Path("data/cache/oi_snapshot.json")


def load_oi_snapshot(path: Path | str = OI_SNAPSHOT_PATH) -> dict[str, Any]:
    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_oi_snapshot(snapshot: dict[str, Any], path: Path | str = OI_SNAPSHOT_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)
