from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unicodedata
from .classifier import classify
from .hashing import sha256_file
from .metadata import resolve_datetime
from .models import PlannedFile
from .scanner import scan_files

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _path_key(path: Path) -> str:
    """Approximate case/Unicode-insensitive filesystem matching for planned names."""
    return unicodedata.normalize("NFC", str(path)).casefold()


def _portable_filename(filename: str) -> str:
    """Make a source filename valid on Windows, macOS, and common removable drives."""
    invalid = set('<>:"/\\|?*')
    safe = "".join("_" if char in invalid or ord(char) < 32 else char for char in filename)
    safe = safe.rstrip(" .")
    if not safe or safe in {".", ".."}:
        safe = "unnamed-file"
    stem = Path(safe).stem
    if stem.rstrip(" .").upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}"
    # Keep individual path components below common filesystem limits while preserving
    # the extension. A collision is resolved later by the standard suffix strategy.
    if len(safe.encode("utf-8", errors="ignore")) > 240:
        suffix = Path(safe).suffix
        stem = Path(safe).stem
        budget = max(1, 230 - len(suffix.encode("utf-8", errors="ignore")))
        while len(stem.encode("utf-8", errors="ignore")) > budget:
            stem = stem[:-1]
        safe = stem + suffix
    return safe


def _destination_for(root: Path, category: str, stamp: datetime | None, filename: str, unknown_folder: str) -> Path:
    if stamp is None:
        return root / category / unknown_folder / filename
    return root / category / f"{stamp.year:04d}" / MONTHS[stamp.month - 1] / filename


def build_plan(sources: list[Path], destination: Path, config: dict) -> list[PlannedFile]:
    org = config["organization"]
    unknown = str(org.get("unknown_date_folder", "UnknownDate"))
    policy = str(org.get("date_policy", "metadata_then_modified"))
    include_hidden = bool(org.get("include_hidden", False))
    template = str(config["duplicates"].get("rename_template", "{stem} ({number}){suffix}"))
    destination_hashes: set[str] = set()
    known_hashes: dict[str, str] = {}
    if destination.exists():
        for path in scan_files([destination], include_hidden=True):
            # A crash can leave a verified-but-unpublished temporary file. Never treat it
            # as a completed destination copy; the next run should retry the intended name.
            if path.name.startswith(".storage-organizer-") and path.name.endswith(".partial"):
                continue
            try:
                digest = sha256_file(path)
                known_hashes[str(path)] = digest
                destination_hashes.add(digest)
            except OSError:
                continue
    plan: list[PlannedFile] = []
    reserved_paths: set[str] = set()
    planned_hashes: set[str] = set()
    for source in scan_files(sources, include_hidden=include_hidden):
        try:
            digest = sha256_file(source)
            stamp = resolve_datetime(source, policy)
        except OSError as exc:
            raise OSError(f"Unable to read source file: {source}: {exc}") from exc
        category = classify(source)
        target = _destination_for(destination, category, stamp, _portable_filename(source.name), unknown)
        year = stamp.year if stamp else None
        month = MONTHS[stamp.month - 1] if stamp else None
        if digest in destination_hashes or digest in planned_hashes:
            plan.append(PlannedFile(source, target, category, year, month, digest, "skip_identical", "Identical content already exists in destination or this run"))
            continue

        # Resolve existing-file and same-run name collisions without overwriting.
        original_target = target
        number = 1
        while target.exists() or _path_key(target) in reserved_paths:
            if target.exists():
                try:
                    existing_hash = known_hashes.get(str(target)) or sha256_file(target)
                    known_hashes[str(target)] = existing_hash
                    if existing_hash == digest:
                        target = None  # type: ignore[assignment]
                        break
                except OSError:
                    pass
            candidate_name = template.format(stem=original_target.stem, number=number, suffix=original_target.suffix)
            target = original_target.with_name(candidate_name)
            number += 1
            if number > 1_000_000:
                raise RuntimeError(f"Could not find a collision-free filename for {original_target}")
        if target is None:
            plan.append(PlannedFile(source, original_target, category, year, month, digest, "skip_identical", "Identical content already exists at target"))
            continue
        reserved_paths.add(_path_key(target))
        planned_hashes.add(digest)
        plan.append(PlannedFile(source, target, category, year, month, digest, "copy", "Ready to copy"))
    return plan
