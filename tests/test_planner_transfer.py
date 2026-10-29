from __future__ import annotations

from datetime import datetime
from pathlib import Path

from storage_organizer.config import DEFAULT_CONFIG
from storage_organizer.hashing import sha256_file
from storage_organizer.organizer import organize
from storage_organizer.planner import build_plan
from storage_organizer.transfer import execute_plan


def config_copy():
    return {section: values.copy() for section, values in DEFAULT_CONFIG.items()}


def test_creates_category_year_month_and_preserves_source(tmp_path, make_file):
    source = tmp_path / "drive" / "DCIM" / "trip.jpg"
    make_file(source, b"mock image bytes", datetime(2025, 3, 14, 12))
    destination = tmp_path / "output"
    summary, plan = organize([source.parents[1]], destination)
    target = destination / "Photos" / "2025" / "March" / "trip.jpg"
    assert target.read_bytes() == b"mock image bytes"
    assert source.read_bytes() == b"mock image bytes"
    assert summary.copied == 1 and summary.failed == 0
    assert plan[0].destination == target


def test_dry_plan_does_not_create_destination(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "a.txt", b"text")
    destination = tmp_path / "not-created"
    plan = build_plan([source], destination, config_copy())
    assert len(plan) == 1
    assert not destination.exists()


def test_identical_content_already_anywhere_in_destination_is_skipped(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "same.txt", b"identical")
    make_file(destination / "somewhere" / "already.txt", b"identical")
    plan = build_plan([source], destination, config_copy())
    assert plan[0].action == "skip_identical"
    summary = execute_plan(plan)
    assert summary.skipped_identical == 1
    assert not (destination / "Documents" / "2025" / "March" / "same.txt").exists()


def test_different_content_same_filename_is_renamed(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "one" / "report.txt", b"first")
    make_file(source / "two" / "report.txt", b"second")
    plan = build_plan([source], destination, config_copy())
    targets = [p.destination.name for p in plan if p.action == "copy"]
    assert sorted(targets) == ["report (1).txt", "report.txt"]
    summary = execute_plan(plan)
    assert summary.copied == 2
    files = list((destination / "Documents" / "2025" / "March").glob("*.txt"))
    assert len(files) == 2
    assert {p.read_bytes() for p in files} == {b"first", b"second"}


def test_repeat_run_skips_existing_content(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "doc.pdf", b"mock pdf")
    first, _ = organize([source], destination)
    second, _ = organize([source], destination)
    assert first.copied == 1
    assert second.skipped_identical == 1
    assert second.copied == 0


def test_hash_matches_copied_file(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    original = make_file(source / "file.bin", b"x" * 5000)
    summary, plan = organize([source], destination)
    assert summary.failed == 0
    assert sha256_file(original) == sha256_file(plan[0].destination)


def test_unknown_date_uses_fallback_folder(tmp_path, make_file, monkeypatch):
    import storage_organizer.planner as planner
    source = tmp_path / "source"
    make_file(source / "photo.png", b"mock png")
    monkeypatch.setattr(planner, "resolve_datetime", lambda *_args, **_kwargs: None)
    plan = planner.build_plan([source], tmp_path / "destination", config_copy())
    assert plan[0].destination.parts[-3:] == ("Photos", "UnknownDate", "photo.png")
    assert plan[0].year is None and plan[0].month is None


def test_source_duplicate_content_is_not_copied_twice(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "one.txt", b"same bytes")
    make_file(source / "two.txt", b"same bytes")
    plan = build_plan([source], destination, config_copy())
    assert sum(p.action == "copy" for p in plan) == 1
    assert sum(p.action == "skip_identical" for p in plan) == 1


def test_existing_different_file_is_preserved_and_new_copy_renamed(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "notes.txt", b"new content")
    existing = destination / "Documents" / "2025" / "March" / "notes.txt"
    make_file(existing, b"existing content")
    summary, plan = organize([source], destination)
    assert summary.copied == 1
    assert existing.read_bytes() == b"existing content"
    assert plan[0].destination.name == "notes (1).txt"
    assert plan[0].destination.read_bytes() == b"new content"


def test_cancel_event_stops_between_files(tmp_path, make_file):
    import threading
    from storage_organizer.transfer import execute_plan
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "one.txt", b"one")
    make_file(source / "two.txt", b"two")
    plan = build_plan([source], destination, config_copy())
    event = threading.Event()
    def progress(done, total, item, summary):
        event.set()
    summary = execute_plan(plan, cancel_event=event, progress=progress)
    assert summary.copied == 1
    assert summary.cancelled is True
    assert sum(1 for p in destination.rglob("*.txt")) == 1


def test_metadata_date_is_preferred_and_modified_policy_skips_metadata(tmp_path, make_file, monkeypatch):
    from datetime import datetime
    import storage_organizer.metadata as metadata
    source = make_file(tmp_path / "photo.jpg", b"mock bytes", datetime(2025, 1, 1))
    embedded = datetime(2020, 7, 9, 10, 30)
    monkeypatch.setattr(metadata, "embedded_datetime", lambda _path: embedded)
    assert metadata.resolve_datetime(source, "metadata_then_modified") == embedded
    assert metadata.resolve_datetime(source, "modified").year == 2025


def test_crash_leftover_partial_does_not_count_as_completed_duplicate(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "notes.txt", b"recover me")
    make_file(destination / ".storage-organizer-crash.partial", b"recover me")
    plan = build_plan([source], destination, config_copy())
    assert plan[0].action == "copy"
    summary = execute_plan(plan)
    assert summary.copied == 1
    assert (destination / "Documents" / "2025" / "March" / "notes.txt").read_bytes() == b"recover me"


def test_portable_filename_rules_are_applied(tmp_path, make_file):
    from storage_organizer.planner import build_plan
    source = tmp_path / "source"
    make_file(source / "CON.txt", b"reserved name")
    plan = build_plan([source], tmp_path / "destination", config_copy())
    assert plan[0].destination.name == "_CON.txt"


def test_transfer_refuses_destination_parent_symlink_inserted_after_plan(tmp_path, make_file):
    import pytest
    from storage_organizer.transfer import TransferError, copy_one
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "photo.jpg", b"photo")
    plan = build_plan([source], destination, config_copy())
    outside = tmp_path / "outside"
    outside.mkdir()
    destination.mkdir(parents=True)
    target_category = destination / "Photos"
    try:
        target_category.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this platform")
    with pytest.raises(TransferError, match="symlink/junction"):
        copy_one(plan[0])
    assert list(outside.iterdir()) == []


def test_invalid_cross_platform_filename_is_sanitized(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "bad:name.txt", b"content")
    plan = build_plan([source], tmp_path / "destination", config_copy())
    assert plan[0].destination.name == "bad_name.txt"


def test_transfer_refuses_symlink_as_final_destination(tmp_path, make_file):
    import pytest
    from storage_organizer.transfer import TransferError, copy_one
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    outside = tmp_path / "outside.txt"
    make_file(source / "note.txt", b"new")
    make_file(outside, b"outside stays unchanged")
    plan = build_plan([source], destination, config_copy())
    target = plan[0].destination
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this platform")
    with pytest.raises(TransferError, match="symlink/junction destination"):
        copy_one(plan[0])
    assert outside.read_bytes() == b"outside stays unchanged"


def test_final_verification_failure_does_not_delete_destination_or_source(tmp_path, make_file, monkeypatch):
    import pytest
    import storage_organizer.transfer as transfer
    from storage_organizer.transfer import TransferError
    source = tmp_path / "source"
    original = make_file(source / "note.txt", b"expected")
    destination = tmp_path / "destination"
    plan = build_plan([source], destination, config_copy())
    expected_digest = plan[0].sha256
    real_hash = transfer.sha256_file

    def controlled_hash(path):
        if path == plan[0].destination:
            return "not-the-expected-hash"
        if path.suffix == ".partial":
            return expected_digest
        return real_hash(path)

    monkeypatch.setattr(transfer, "sha256_file", controlled_hash)
    with pytest.raises(TransferError, match="left in place for inspection"):
        transfer.copy_one(plan[0])
    assert original.read_bytes() == b"expected"
    assert plan[0].destination.exists()


def test_atomic_publish_falls_back_when_hardlinks_are_unavailable(tmp_path, monkeypatch):
    import errno
    import storage_organizer.transfer as transfer
    temp_path = tmp_path / ".storage-organizer-test.partial"
    target = tmp_path / "published.bin"
    temp_path.write_bytes(b"verified bytes")

    def no_hardlinks(*_args, **_kwargs):
        raise OSError(errno.EOPNOTSUPP, "hard links unsupported")

    monkeypatch.setattr(transfer.os, "link", no_hardlinks)
    transfer._publish_without_overwrite(temp_path, target)
    assert target.read_bytes() == b"verified bytes"
    assert not temp_path.exists()


def test_atomic_publish_never_overwrites_existing_target(tmp_path):
    import pytest
    from storage_organizer.transfer import _publish_without_overwrite
    temp_path = tmp_path / ".storage-organizer-test.partial"
    target = tmp_path / "published.bin"
    temp_path.write_bytes(b"new bytes")
    target.write_bytes(b"existing bytes")
    with pytest.raises(FileExistsError):
        _publish_without_overwrite(temp_path, target)
    assert target.read_bytes() == b"existing bytes"
    assert temp_path.exists()
