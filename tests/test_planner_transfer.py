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
