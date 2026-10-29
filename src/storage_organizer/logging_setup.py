from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .config import user_data_dir


def setup_logging(directory: Path | None = None, verbose: bool = False) -> logging.Logger:
    log_dir = directory or (user_data_dir() / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("storage_organizer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(log_dir / "organizer.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
