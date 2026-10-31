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


def test_invalid_cross_platform_filename_is_sanitized():
    from storage_organizer.planner import _portable_filename

    assert _portable_filename("bad:name.txt") == "bad_name.txt"
    assert _portable_filename("bad|name.txt") == "bad_name.txt"
    assert _portable_filename("bad?.txt") == "bad_.txt"


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


def test_planner_distinguishes_destination_skips_from_source_duplicates(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    first = make_file(source / "one.txt", b"repeated source content")
    second = make_file(source / "two.txt", b"repeated source content")
    existing = make_file(destination / "archive" / "already.txt", b"already stored")
    third = make_file(source / "three.txt", b"already stored")

    plan = build_plan([source], destination, config_copy())
    by_source = {item.source: item for item in plan}

    assert by_source[first].action == "copy"
    assert by_source[second].action == "skip_identical"
    assert by_source[second].skip_reason == "source_duplicate"
    assert by_source[second].duplicate_of == first
    assert by_source[third].action == "skip_identical"
    assert by_source[third].skip_reason == "destination"
    assert by_source[third].duplicate_of == existing


def test_execute_plan_returns_one_terminal_result_per_file(tmp_path, make_file):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "a-copy.txt", b"unique")
    make_file(source / "b-duplicate.txt", b"unique")
    make_file(source / "c-present.txt", b"already there")
    make_file(destination / "old" / "present.txt", b"already there")

    plan = build_plan([source], destination, config_copy())
    summary = execute_plan(plan)
    results = {item.source.name: item for item in summary.files}

    assert summary.scanned == len(plan) == len(summary.files)
    assert results["a-copy.txt"].status == "copied"
    assert results["b-duplicate.txt"].status == "duplicate"
    assert results["b-duplicate.txt"].duplicate_of == results["a-copy.txt"].source
    assert results["c-present.txt"].status == "skipped"
    assert summary.copied == 1
    assert summary.duplicates == 1
    assert summary.skipped_identical == 1
    assert summary.failed == 0
    assert summary.cancelled_files == 0
    assert summary.scanned == (
        summary.copied
        + summary.duplicates
        + summary.skipped_identical
        + summary.failed
        + summary.cancelled_files
    )


def test_execute_plan_records_copying_and_terminal_file_events(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "file.txt", b"payload")
    plan = build_plan([source], tmp_path / "destination", config_copy())
    events = []

    summary = execute_plan(
        plan,
        file_progress=lambda result, done, total, _summary: events.append(
            (result.status, done, total)
        ),
    )

    assert [event[0] for event in events] == ["copying", "copied"]
    assert events[0][1:] == (0, 1)
    assert events[1][1:] == (1, 1)
    assert summary.files[0].status == "copied"


def test_execute_plan_records_per_file_error_and_continues(tmp_path, make_file, monkeypatch):
    import storage_organizer.transfer as transfer

    source = tmp_path / "source"
    make_file(source / "a-broken.txt", b"broken")
    make_file(source / "b-good.txt", b"good")
    plan = build_plan([source], tmp_path / "destination", config_copy())
    real_copy_one = transfer.copy_one

    def fail_one(item, verify_hash=True):
        if item.source.name == "a-broken.txt":
            raise transfer.TransferError("simulated write failure")
        return real_copy_one(item, verify_hash=verify_hash)

    monkeypatch.setattr(transfer, "copy_one", fail_one)
    summary = transfer.execute_plan(plan)
    results = {item.source.name: item for item in summary.files}

    assert results["a-broken.txt"].status == "error"
    assert "simulated write failure" in results["a-broken.txt"].reason
    assert str(source / "a-broken.txt") in summary.errors[0]
    assert results["b-good.txt"].status == "copied"
    assert summary.failed == 1
    assert summary.copied == 1
    assert summary.scanned == 2


def test_cancelled_files_are_explicit_in_results(tmp_path, make_file):
    import threading

    source = tmp_path / "source"
    make_file(source / "a.txt", b"one")
    make_file(source / "b.txt", b"two")
    make_file(source / "c.txt", b"three")
    plan = build_plan([source], tmp_path / "destination", config_copy())
    cancel_event = threading.Event()
    seen = []

    def on_file(result, done, total, _summary):
        seen.append(result.status)
        if result.status == "copied":
            cancel_event.set()

    summary = execute_plan(plan, cancel_event=cancel_event, file_progress=on_file)

    assert summary.cancelled is True
    assert summary.copied == 1
    assert summary.cancelled_files == 2
    assert [result.status for result in summary.files].count("cancelled") == 2
    assert all(result.reason for result in summary.files)
    assert summary.scanned == (
        summary.copied
        + summary.duplicates
        + summary.skipped_identical
        + summary.failed
        + summary.cancelled_files
    )


def test_file_result_is_json_serializable(tmp_path):
    import json
    from storage_organizer.models import FileResult

    result = FileResult(
        source=tmp_path / "source.txt",
        destination=tmp_path / "destination.txt",
        status="duplicate",
        reason="Same bytes",
        sha256="abc123",
        duplicate_of=tmp_path / "original.txt",
    )
    payload = result.to_dict()

    assert json.loads(json.dumps(payload)) == {
        "source": str(tmp_path / "source.txt"),
        "destination": str(tmp_path / "destination.txt"),
        "status": "duplicate",
        "reason": "Same bytes",
        "sha256": "abc123",
        "duplicate_of": str(tmp_path / "original.txt"),
    }


def test_unreadable_source_is_a_per_file_error_and_other_files_continue(
    tmp_path, make_file, monkeypatch
):
    import storage_organizer.planner as planner_module

    source = tmp_path / "source"
    broken = make_file(source / "a-unreadable.txt", b"cannot read")
    make_file(source / "b-readable.txt", b"copy this")
    real_hash = planner_module.sha256_file

    def selective_hash(path):
        if path == broken:
            raise PermissionError("permission denied in test")
        return real_hash(path)

    monkeypatch.setattr(planner_module, "sha256_file", selective_hash)
    plan = planner_module.build_plan([source], tmp_path / "destination", config_copy())
    by_source = {item.source.name: item for item in plan}

    assert by_source["a-unreadable.txt"].action == "error"
    assert "permission denied in test" in by_source["a-unreadable.txt"].reason
    assert by_source["b-readable.txt"].action == "copy"

    summary = execute_plan(plan)
    results = {item.source.name: item for item in summary.files}
    assert results["a-unreadable.txt"].status == "error"
    assert results["b-readable.txt"].status == "copied"
    assert summary.failed == 1
    assert summary.copied == 1


def test_organize_emits_plan_before_live_file_statuses(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "a.txt", b"payload")
    events = []

    summary, plan = organize(
        [source],
        tmp_path / "destination",
        plan_ready=lambda current_plan: events.append(("plan", len(current_plan))),
        file_progress=lambda result, done, total, _summary: events.append(
            (result.status, done, total)
        ),
    )

    assert events[0] == ("plan", 1)
    assert [event[0] for event in events[1:]] == ["copying", "copied"]
    assert summary.copied == 1
    assert len(plan) == 1


def test_cancellation_preserves_already_known_skip_and_planning_error_results(
    tmp_path, make_file, monkeypatch
):
    import threading
    import storage_organizer.planner as planner_module

    source = tmp_path / "source"
    make_file(source / "a-duplicate.txt", b"duplicate bytes")
    unreadable = make_file(source / "b-unreadable.txt", b"cannot read")
    make_file(source / "c-copy.txt", b"copy bytes")
    make_file(tmp_path / "destination" / "stored.txt", b"duplicate bytes")
    real_hash = planner_module.sha256_file

    def selective_hash(path):
        if path == unreadable:
            raise PermissionError("read denied")
        return real_hash(path)

    monkeypatch.setattr(planner_module, "sha256_file", selective_hash)
    plan = build_plan([source], tmp_path / "destination", config_copy())
    cancel_event = threading.Event()
    cancel_event.set()
    summary = execute_plan(plan, cancel_event=cancel_event)
    results = {item.source.name: item for item in summary.files}

    assert results["a-duplicate.txt"].status == "skipped"
    assert results["b-unreadable.txt"].status == "error"
    assert results["c-copy.txt"].status == "cancelled"
    assert summary.skipped_identical == 1
    assert summary.failed == 1
    assert summary.cancelled_files == 1
    assert summary.scanned == 3
