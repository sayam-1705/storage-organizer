from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Action = Literal["copy", "skip_identical"]

@dataclass(frozen=True)
class PlannedFile:
    source: Path
    destination: Path
    category: str
    year: int | None
    month: str | None
    sha256: str
    action: Action
    reason: str = ""

@dataclass
class RunSummary:
    scanned: int = 0
    planned: int = 0
    copied: int = 0
    skipped_identical: int = 0
    failed: int = 0
    cancelled: bool = False
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
