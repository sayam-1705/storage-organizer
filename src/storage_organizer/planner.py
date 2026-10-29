from __future__ import annotations

from datetime import datetime
from pathlib import Path
from .classifier import classify
from .hashing import sha256_file
from .metadata import resolve_datetime
from .models import PlannedFile
from .scanner import scan_files

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _destination_for(root: Path, category: str, stamp: datetime | None, filename: str, unknown_folder: str) -> Path:
    if stamp is None:
        return root / category / unknown_folder / filename
    return root / category / f"{stamp.year:04d}" / MONTHS[stamp.month - 1] / filename


def _next_available(path: Path, digest: str, known_hashes: dict[str, str], template: str) -> tuple[Path, bool]:
    """Return a non-conflicting name and whether identical content is already present."""
    if not path.exists():
        return path, False
    try:
        existing_hash = known_hashes.get(str(path))
        if existing_hash is None:
            existing_hash = sha256_file(path)
            known_hashes[str(path)] = existing_hash
        if existing_hash == digest:
            return path, True
    except OSError:
        pass
    number = 1
    while number < 1_000_000:
        name = template.format(stem=path.stem, number=number, suffix=path.suffix)
        candidate = path.with_name(name)
        if not candidate.exists():
            return candidate, False
        try:
            candidate_hash = known_hashes.get(str(candidate)) or sha256_file(candidate)
            known_hashes[str(candidate)] = candidate_hash
            if candidate_hash == digest:
                return candidate, True
        except OSError:
            pass
        number += 1
    raise RuntimeError(f"Could not find a collision-free filename for {path}")


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
        target = _destination_for(destination, category, stamp, source.name, unknown)
        year = stamp.year if stamp else None
        month = MONTHS[stamp.month - 1] if stamp else None
        if digest in destination_hashes or digest in planned_hashes:
            plan.append(PlannedFile(source, target, category, year, month, digest, "skip_identical", "Identical content already exists in destination or this run"))
            continue

        # Resolve existing-file and same-run name collisions without overwriting.
        original_target = target
        number = 1
        while target.exists() or str(target).casefold() in reserved_paths:
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
        reserved_paths.add(str(target).casefold())
        planned_hashes.add(digest)
        plan.append(PlannedFile(source, target, category, year, month, digest, "copy", "Ready to copy"))
    return plan
