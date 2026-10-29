from __future__ import annotations

import os
import re
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
            if section not in config:
                raise ValueError(f"Unknown configuration section: {section}")
            if not isinstance(values, dict):
                raise ValueError(f"Configuration section [{section}] must be a table")
            unknown_keys = set(values) - set(config[section])
            if unknown_keys:
                raise ValueError(f"Unknown key(s) in [{section}]: {', '.join(sorted(unknown_keys))}")
            config[section].update(values)
    organization = config["organization"]
    duplicates = config["duplicates"]
    transfer = config["transfer"]
    if organization.get("date_policy") not in {"metadata_then_modified", "modified"}:
        raise ValueError("organization.date_policy must be metadata_then_modified or modified")
    if not isinstance(organization.get("include_hidden"), bool):
        raise ValueError("organization.include_hidden must be true or false")
    unknown_folder = organization.get("unknown_date_folder")
    if not isinstance(unknown_folder, str) or not unknown_folder.strip():
        raise ValueError("organization.unknown_date_folder must be a non-empty folder name")
    if unknown_folder in {".", ".."} or any(char in unknown_folder for char in ("/", "\\", "\0", "<", ">", ":", '"', "|", "?", "*")):
        raise ValueError("organization.unknown_date_folder must be a single safe folder name")
    if unknown_folder.rstrip(" .") != unknown_folder:
        raise ValueError("organization.unknown_date_folder cannot end in a dot or space")
    if unknown_folder.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("organization.unknown_date_folder cannot be a reserved Windows device name")
    if not isinstance(transfer.get("verify_hash"), bool):
        raise ValueError("transfer.verify_hash must be true or false")
    if duplicates.get("strategy") != "sha256":
        raise ValueError("Only the sha256 duplicate strategy is supported")
    template = duplicates.get("rename_template")
    if not isinstance(template, str) or not template:
        raise ValueError("duplicates.rename_template must be a non-empty string")
    if any(char in template for char in ("/", "\\", "\0", "<", ">", ":", '"', "|", "?", "*")):
        raise ValueError("duplicates.rename_template must not contain path separators or invalid filename characters")
    if not re.fullmatch(r"(?:[^{}]|\{(?:stem|number|suffix)\})+", template):
        raise ValueError("duplicates.rename_template may only use {stem}, {number}, and {suffix} placeholders")
    if "{number}" not in template or "{stem}" not in template or "{suffix}" not in template:
        raise ValueError("duplicates.rename_template must include {stem}, {number}, and {suffix}")
    logging_directory = config["logging"].get("directory")
    if logging_directory is not None and not isinstance(logging_directory, str):
        raise ValueError("logging.directory must be a path string")
    return config


def ensure_user_data_dir() -> Path:
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
