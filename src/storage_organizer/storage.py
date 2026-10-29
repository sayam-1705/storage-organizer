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
    destination = destination.expanduser()
    # Inspect the user-supplied spelling before resolve() follows symlinks.
    _reject_symlinked_existing_parents(destination.absolute())
    destination = destination.resolve(strict=False)
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
    # Recheck the normalized path too; destination ancestors can be changed after validation.
    _reject_symlinked_existing_parents(destination)
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
        stats = os.statvfs(probe)
        return stats.f_bavail * stats.f_frsize  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        try:
            import shutil
            return shutil.disk_usage(probe).free
        except OSError:
            return None


def _is_link_or_junction(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction()) if is_junction is not None else False
    except OSError:
        return True


def _reject_symlinked_existing_parents(path: Path) -> None:
    """Reject existing symlink/junction components in a destination path."""
    current = path
    missing: list[Path] = []
    while not current.exists() and current != current.parent:
        missing.append(current)
        current = current.parent
    if _is_link_or_junction(current):
        raise StorageValidationError(f"Destination must not traverse a symlink or junction: {current}")
    for component in reversed(missing):
        if component.exists() and _is_link_or_junction(component):
            raise StorageValidationError(f"Destination must not traverse a symlink or junction: {component}")
