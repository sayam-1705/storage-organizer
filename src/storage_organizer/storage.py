from __future__ import annotations

import os
from pathlib import Path


class StorageValidationError(ValueError):
    pass


def validate_paths(sources: list[Path], destination: Path) -> tuple[list[Path], Path]:
    if not sources:
        raise StorageValidationError("Select at least one source drive or folder.")
    normalized_sources: list[Path] = []
    for source in sources:
        source = source.expanduser()
        if not source.exists():
            raise StorageValidationError(f"Source does not exist: {source}")
        source = source.resolve(strict=True)
        if not source.is_dir():
            raise StorageValidationError(f"Source must be a directory or mounted drive: {source}")
        normalized_sources.append(source)
    destination = destination.expanduser().resolve(strict=False)
    if destination.exists() and not destination.is_dir():
        raise StorageValidationError(f"Destination must be a directory or a new directory path: {destination}")
    for source in normalized_sources:
        try:
            common = os.path.commonpath([str(source), str(destination)])
        except ValueError:  # Different Windows drives
            continue
        if Path(common) == source or Path(common) == destination:
            raise StorageValidationError(
                f"Source and destination must not overlap. Source: {source}; destination: {destination}"
            )
    # Deduplicate sources and reject nested source selections to avoid processing files twice.
    unique = sorted(set(normalized_sources), key=lambda p: (len(p.parts), str(p).casefold()))
    filtered: list[Path] = []
    for candidate in unique:
        if not any(parent == candidate or parent in candidate.parents for parent in filtered):
            filtered.append(candidate)
    return filtered, destination


def available_bytes(path: Path) -> int | None:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return os.statvfs(probe).f_bavail * os.statvfs(probe).f_frsize  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        try:
            import shutil
            return shutil.disk_usage(probe).free
        except OSError:
            return None
