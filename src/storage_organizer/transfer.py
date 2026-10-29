from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from .hashing import sha256_file
from .models import PlannedFile, RunSummary


class TransferError(RuntimeError):
    pass


def _publish_without_overwrite(temp_path: Path, target: Path) -> None:
    """Publish verified temporary content without replacing an existing file."""
    try:
        # Same-directory hard link is atomic and fails if target already exists.
        os.link(temp_path, target)
        temp_path.unlink()
        return
    except FileExistsError:
        raise
    except (OSError, NotImplementedError):
        # Fallback for filesystems without hard-link support. O_EXCL prevents overwrite.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "wb") as output, temp_path.open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        temp_path.unlink(missing_ok=True)


def copy_one(item: PlannedFile, verify_hash: bool = True) -> str:
    if item.action == "skip_identical":
        return "skipped"
    item.destination.parent.mkdir(parents=True, exist_ok=True)
    # A final preflight check handles changes made since the plan was created.
    if item.destination.exists():
        if item.destination.is_file() and sha256_file(item.destination) == item.sha256:
            return "skipped"
        raise TransferError(f"Destination appeared after planning; refusing to overwrite: {item.destination}")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".storage-organizer-", suffix=".partial", dir=item.destination.parent, delete=False) as temp:
            temp_name = temp.name
            with item.source.open("rb") as source:
                shutil.copyfileobj(source, temp, length=1024 * 1024)
            temp.flush()
            os.fsync(temp.fileno())
        temp_path = Path(temp_name)
        if item.source.stat().st_size != temp_path.stat().st_size:
            raise TransferError(f"Size verification failed for {item.source}")
        if verify_hash and sha256_file(temp_path) != item.sha256:
            raise TransferError(f"Hash verification failed for {item.source}")
        try:
            _publish_without_overwrite(temp_path, item.destination)
        except FileExistsError:
            if item.destination.is_file() and sha256_file(item.destination) == item.sha256:
                return "skipped"
            raise TransferError(f"Destination conflict; refusing to overwrite: {item.destination}")
        if verify_hash and sha256_file(item.destination) != item.sha256:
            # Preserve source and remove only the newly published invalid copy.
            item.destination.unlink(missing_ok=True)
            raise TransferError(f"Final verification failed for {item.destination}")
        try:
            shutil.copystat(item.source, item.destination, follow_symlinks=False)
        except (OSError, NotImplementedError):
            pass
        return "copied"
    except TransferError:
        raise
    except OSError as exc:
        raise TransferError(f"Could not copy {item.source} to {item.destination}: {exc}") from exc
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


def execute_plan(plan: list[PlannedFile], verify_hash: bool = True, logger=None, progress=None, cancel_event=None) -> RunSummary:
    summary = RunSummary(scanned=len(plan), planned=sum(item.action == "copy" for item in plan))
    for index, item in enumerate(plan, start=1):
        if cancel_event is not None and cancel_event.is_set():
            summary.cancelled = True
            if logger:
                logger.info("Operation cancelled by user between files")
            break
        try:
            result = copy_one(item, verify_hash=verify_hash)
            if result == "copied":
                summary.copied += 1
                message = f"COPIED {item.source} -> {item.destination}"
            else:
                summary.skipped_identical += 1
                message = f"SKIPPED identical {item.source}"
            if logger:
                logger.info(message)
        except Exception as exc:  # keep processing other files after an individual failure
            summary.failed += 1
            message = f"FAILED {item.source}: {exc}"
            summary.errors.append(message)
            if logger:
                logger.exception(message)
        if progress:
            progress(index, len(plan), item, summary)
    return summary
