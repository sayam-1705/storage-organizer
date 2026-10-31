from __future__ import annotations

import ctypes
import errno
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from .hashing import sha256_file
from .models import FileResult, PlannedFile, RunSummary


class TransferError(RuntimeError):
    pass


def _rename_noreplace(source: Path, target: Path) -> bool:
    """Atomically rename without replacing an existing target where the OS supports it.

    Returns False only when the platform has no supported no-replace rename primitive.
    """
    if os.name == "nt":
        # Windows MoveFile/rename semantics fail when the destination already exists.
        os.rename(source, target)
        return True

    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int
            result = renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)  # AT_FDCWD, RENAME_NOREPLACE
            if result == 0:
                return True
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise FileExistsError(error, os.strerror(error), str(target))
            if error not in {errno.ENOSYS, errno.EINVAL, getattr(errno, "EOPNOTSUPP", errno.EINVAL)}:
                raise OSError(error, os.strerror(error), str(target))

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        renamex_np = getattr(libc, "renamex_np", None)
        if renamex_np is not None:
            renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            renamex_np.restype = ctypes.c_int
            result = renamex_np(os.fsencode(source), os.fsencode(target), 0x00000004)  # RENAME_EXCL
            if result == 0:
                return True
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise FileExistsError(error, os.strerror(error), str(target))
            if error not in {errno.ENOSYS, errno.EINVAL, getattr(errno, "EOPNOTSUPP", errno.EINVAL)}:
                raise OSError(error, os.strerror(error), str(target))
    return False


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
        # Hard links are unavailable on some removable filesystems. Prefer an atomic
        # no-replace rename, supported on Windows, Linux, and macOS.
        try:
            if _rename_noreplace(temp_path, target):
                return
        except FileExistsError:
            raise
        except OSError as exc:
            if exc.errno not in {errno.ENOSYS, errno.EINVAL, getattr(errno, "EOPNOTSUPP", errno.EINVAL)}:
                raise

        # Last-resort fallback for unusual platforms without a no-replace rename API.
        # O_EXCL still prevents overwriting, although a power loss can expose a partial
        # final file on such platforms. The source remains intact and retry is safe.
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


def _fsync_directory(path: Path) -> None:
    """Best-effort sync of a directory entry after publishing a copied file."""
    if os.name == "nt":
        return
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY)
        os.fsync(descriptor)
    except OSError:
        # Some removable/network filesystems do not support directory fsync.
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _reject_symlinked_parents(path: Path) -> None:
    """Defend against a symlink/junction inserted after path validation."""
    current = path
    while current != current.parent:
        if current.exists():
            try:
                is_junction = getattr(current, "is_junction", None)
                if current.is_symlink() or (is_junction is not None and is_junction()):
                    raise TransferError(f"Refusing to write through symlink/junction: {current}")
            except OSError as exc:
                raise TransferError(f"Cannot validate destination path {current}: {exc}") from exc
        current = current.parent


def _copy_stream(source, destination, progress=None, chunk_size: int = 1024 * 1024) -> int:
    """Copy a stream in bounded chunks and optionally report bytes written."""
    copied = 0
    while True:
        chunk = source.read(chunk_size)
        if not chunk:
            break
        destination.write(chunk)
        copied += len(chunk)
        if progress:
            progress(copied)
    return copied


def copy_one(
    item: PlannedFile,
    verify_hash: bool = True,
    copy_progress=None,
) -> str:
    if item.action == "skip_identical":
        return "skipped"
    if item.source.is_symlink() or not item.source.is_file():
        raise TransferError(f"Source is no longer a regular, non-symlink file: {item.source}")
    _reject_symlinked_parents(item.destination.parent)
    try:
        is_junction = getattr(item.destination, "is_junction", None)
        if item.destination.is_symlink() or (is_junction is not None and is_junction()):
            raise TransferError(f"Refusing to write to a symlink/junction destination: {item.destination}")
    except OSError as exc:
        raise TransferError(f"Cannot validate destination {item.destination}: {exc}") from exc
    item.destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlinked_parents(item.destination.parent)
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
                _copy_stream(source, temp, progress=copy_progress)
            temp.flush()
            os.fsync(temp.fileno())
        temp_path = Path(temp_name)
        if item.source.stat().st_size != temp_path.stat().st_size:
            raise TransferError(f"Size verification failed for {item.source}")
        if verify_hash and sha256_file(temp_path) != item.sha256:
            raise TransferError(f"Hash verification failed for {item.source}")
        try:
            _publish_without_overwrite(temp_path, item.destination)
            _fsync_directory(item.destination.parent)
        except FileExistsError:
            if item.destination.is_file() and sha256_file(item.destination) == item.sha256:
                return "skipped"
            raise TransferError(f"Destination conflict; refusing to overwrite: {item.destination}")
        if verify_hash and sha256_file(item.destination) != item.sha256:
            # Do not delete a file here: another process may have touched the destination
            # after publication. Preserve evidence and report the mismatch for user review.
            raise TransferError(f"Final verification failed for {item.destination}; file left in place for inspection")
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


def execute_plan(
    plan: list[PlannedFile],
    verify_hash: bool = True,
    logger=None,
    progress=None,
    cancel_event=None,
    file_progress=None,
    transfer_progress=None,
) -> RunSummary:
    """Execute a plan and retain one structured result for every planned file.

    ``progress`` preserves the original callback API and fires once per file after
    its terminal outcome. ``file_progress`` receives ``(result, done, total,
    summary)`` for live status changes, including the transition to ``copying``.
    """
    summary = RunSummary(
        scanned=len(plan),
        planned=sum(item.action == "copy" for item in plan),
        files=[
            FileResult(
                source=item.source,
                destination=item.destination,
                sha256=item.sha256,
                duplicate_of=item.duplicate_of,
            )
            for item in plan
        ],
    )
    total = len(plan)
    done = 0
    started_at = time.monotonic()
    bytes_copied = 0
    total_bytes = 0
    for planned_file in plan:
        if planned_file.action != "copy":
            continue
        try:
            total_bytes += planned_file.source.stat().st_size
        except OSError:
            # The source may disappear after planning. The per-file error result
            # remains authoritative; byte totals are best-effort progress hints.
            continue

    def notify_transfer() -> None:
        if transfer_progress:
            transfer_progress(
                bytes_copied,
                total_bytes,
                max(0.0, time.monotonic() - started_at),
                done,
                total,
            )

    def notify_file(result: FileResult) -> None:
        if file_progress:
            file_progress(result, done, total, summary)

    def notify_legacy(index: int, item: PlannedFile) -> None:
        if progress:
            progress(index, total, item, summary)

    cancellation_logged = False
    notify_transfer()
    for index, (item, file_result) in enumerate(zip(plan, summary.files), start=1):
        # Planning outcomes are already known and should remain visible even when
        # the user cancels the copy phase. Only work that has not started is cancelled.
        if item.action == "error":
            file_result.status = "error"
            file_result.reason = item.reason or f"Unable to plan source file: {item.source}"
            summary.failed += 1
            message = f"FAILED {item.source}: {file_result.reason}"
            summary.errors.append(message)
            done += 1
            notify_file(file_result)
            notify_transfer()
            if logger:
                logger.error(message)
            notify_legacy(index, item)
            continue

        if item.action == "skip_identical":
            if item.skip_reason == "source_duplicate":
                file_result.status = "duplicate"
                file_result.reason = item.reason or "Duplicate content in selected sources"
                summary.duplicates += 1
                message = f"DUPLICATE {item.source}: {file_result.reason}"
            else:
                file_result.status = "skipped"
                file_result.reason = item.reason or "Identical content already exists in destination"
                summary.skipped_identical += 1
                message = f"SKIPPED {item.source}: {file_result.reason}"
            done += 1
            notify_file(file_result)
            notify_transfer()
            if logger:
                logger.info(message)
            notify_legacy(index, item)
            continue

        if cancel_event is not None and cancel_event.is_set():
            summary.cancelled = True
            file_result.status = "cancelled"
            file_result.reason = "Not processed because cancellation was requested"
            summary.cancelled_files += 1
            done += 1
            notify_file(file_result)
            notify_transfer()
            if logger and not cancellation_logged:
                logger.info("Operation cancelled by user between files")
                cancellation_logged = True
            notify_legacy(index, item)
            continue

        file_result.status = "copying"
        file_result.reason = "Copy in progress"
        notify_file(file_result)
        current_file_bytes = 0

        def on_copy_progress(current_bytes: int) -> None:
            nonlocal bytes_copied, current_file_bytes
            increment = max(0, current_bytes - current_file_bytes)
            current_file_bytes = current_bytes
            bytes_copied += increment
            notify_transfer()

        try:
            if transfer_progress:
                result = copy_one(
                    item,
                    verify_hash=verify_hash,
                    copy_progress=on_copy_progress,
                )
            else:
                result = copy_one(item, verify_hash=verify_hash)
            if result == "copied":
                file_result.status = "copied"
                file_result.reason = (
                    "Copied successfully and SHA-256 verified"
                    if verify_hash else "Copied successfully"
                )
                summary.copied += 1
                message = f"COPIED {item.source} -> {item.destination}"
            else:
                file_result.status = "skipped"
                file_result.reason = "Identical content appeared in destination after planning"
                file_result.duplicate_of = item.destination
                summary.skipped_identical += 1
                message = f"SKIPPED identical {item.source}"
            if logger:
                logger.info(message)
        except Exception as exc:  # keep processing other files after an individual failure
            file_result.status = "error"
            file_result.reason = str(exc)
            summary.failed += 1
            message = f"FAILED {item.source}: {exc}"
            summary.errors.append(message)
            if logger:
                logger.exception(message)

        done += 1
        notify_file(file_result)
        notify_transfer()
        notify_legacy(index, item)

    return summary
