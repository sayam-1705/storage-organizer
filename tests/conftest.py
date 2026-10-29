from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture

def make_file():
    def _make_file(path: Path, content: bytes = b"mock data", date: datetime = datetime(2025, 3, 14, 12, 0, 0)) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = date.timestamp()
        os.utime(path, (timestamp, timestamp))
        return path
    return _make_file
