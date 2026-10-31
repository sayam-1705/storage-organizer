from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Action = Literal["copy", "skip_identical", "error"]
FileStatus = Literal[
    "pending", "copying", "copied", "skipped", "duplicate", "error", "cancelled"
]
SkipReason = Literal["destination", "source_duplicate"]


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
    skip_reason: SkipReason | None = None
    duplicate_of: Path | None = None


@dataclass
class FileResult:
    """Structured outcome for one file discovered during an organization run."""

    source: Path
    destination: Path
    status: FileStatus = "pending"
    reason: str = ""
    sha256: str = ""
    duplicate_of: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation of this file result."""
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "status": self.status,
            "reason": self.reason,
            "sha256": self.sha256,
            "duplicate_of": str(self.duplicate_of) if self.duplicate_of else None,
        }


@dataclass
class RunSummary:
    scanned: int = 0
    planned: int = 0
    copied: int = 0
    skipped_identical: int = 0
    duplicates: int = 0
    failed: int = 0
    cancelled_files: int = 0
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)
    files: list[FileResult] = field(default_factory=list)
