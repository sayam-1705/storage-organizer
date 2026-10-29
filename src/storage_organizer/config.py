from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULT_CONFIG = {
    "organization": {"include_hidden": False, "unknown_date_folder": "UnknownDate", "date_policy": "metadata_then_modified"},
    "transfer": {"verify_hash": True},
    "duplicates": {"strategy": "sha256", "rename_template": "{stem} ({number}){suffix}"},
    "logging": {},
}


def user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "storage-organizer"


def load_config(path: Path | None = None) -> dict:
    config = {section: values.copy() for section, values in DEFAULT_CONFIG.items()}
    config_path = path or (user_data_dir() / "config.toml")
    if config_path.exists():
        with config_path.open("rb") as stream:
            loaded = tomllib.load(stream)
        for section, values in loaded.items():
            if isinstance(values, dict) and section in config:
                config[section].update(values)
    if config["organization"].get("date_policy") not in {"metadata_then_modified", "modified"}:
        raise ValueError("organization.date_policy must be metadata_then_modified or modified")
    if not isinstance(config["organization"].get("include_hidden"), bool):
        raise ValueError("organization.include_hidden must be true or false")
    if config["duplicates"].get("strategy") != "sha256":
        raise ValueError("Only the sha256 duplicate strategy is supported")
    return config


def ensure_user_data_dir() -> Path:
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
