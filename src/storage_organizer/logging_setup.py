from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import user_data_dir


def setup_logging(directory: Path | None = None, verbose: bool = False) -> logging.Logger:
    """Configure one rotating local log handler, respecting a requested directory."""
    log_dir = (directory or (user_data_dir() / "logs")).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    target = (log_dir / "organizer.log").resolve(strict=False)
    logger = logging.getLogger("storage_organizer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    existing = None
    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename).resolve(strict=False) == target:
            existing = handler
        else:
            logger.removeHandler(handler)
            try:
                handler.close()
            except OSError:
                pass
    if existing is None:
        handler = RotatingFileHandler(target, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
