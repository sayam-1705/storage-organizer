"""Small JSON preferences file; deliberately not a database."""
from __future__ import annotations

import json
import os
from pathlib import Path
from .config import user_data_dir


def preferences_path() -> Path:
    return user_data_dir() / "preferences.json"


def load_preferences() -> dict[str, str]:
    path = preferences_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {key: value for key, value in data.items() if key in {"source", "destination"} and isinstance(value, str)}
    except (OSError, json.JSONDecodeError):
        return {}


def save_preferences(source: str | None = None, destination: str | None = None) -> None:
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_preferences()
    if source is not None:
        data["source"] = source
    if destination is not None:
        data["destination"] = destination
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)
