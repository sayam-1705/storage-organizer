"""Small JSON preferences file; deliberately not a database."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .config import user_data_dir


def preferences_path() -> Path:
    return user_data_dir() / "preferences.json"


def load_preferences() -> dict[str, str | list[str]]:
    path = preferences_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        result = {
            key: value
            for key, value in data.items()
            if key in {"source", "destination"} and isinstance(value, str)
        }
        sources = data.get("sources")
        if isinstance(sources, list) and all(isinstance(item, str) for item in sources):
            result["sources"] = list(dict.fromkeys(sources))
        return result
    except (OSError, json.JSONDecodeError):
        return {}


def save_preferences(
    source: str | None = None,
    destination: str | None = None,
    sources: list[str] | None = None,
) -> None:
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_preferences()
    if source is not None:
        data["source"] = source
    if sources is not None:
        unique_sources = list(dict.fromkeys(sources))
        data["sources"] = unique_sources
        if unique_sources:
            data["source"] = unique_sources[0]
        else:
            data.pop("source", None)
    if destination is not None:
        data["destination"] = destination
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def recent_runs_path() -> Path:
    return user_data_dir() / "recent-runs.json"


def load_recent_runs(limit: int = 10) -> list[dict]:
    """Load the newest bounded set of operation summaries."""
    try:
        data = json.loads(recent_runs_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)][: max(0, limit)]


def save_recent_run(result: dict, limit: int = 10) -> None:
    """Prepend an operation summary and retain only the newest ``limit`` runs."""
    path = recent_runs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_recent_runs(limit=max(limit, 10_000))
    entries = [result, *previous][: max(1, limit)]
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
