from pathlib import Path
import pytest
from storage_organizer.storage import StorageValidationError, validate_paths


def test_rejects_missing_source(tmp_path):
    with pytest.raises((StorageValidationError, FileNotFoundError)):
        validate_paths([tmp_path / "missing"], tmp_path / "destination")


def test_rejects_same_or_overlapping_paths(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(StorageValidationError):
        validate_paths([source], source)
    with pytest.raises(StorageValidationError):
        validate_paths([source], source / "organized")
    with pytest.raises(StorageValidationError):
        validate_paths([source / "nested"], source)


def test_allows_separate_folders_on_same_drive(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    sources, destination = validate_paths([source], tmp_path / "destination")
    assert sources == [source.resolve()]
    assert destination == (tmp_path / "destination").resolve()


def test_deduplicates_nested_source_selection(tmp_path):
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    sources, _ = validate_paths([nested, source], tmp_path / "destination")
    assert sources == [source.resolve()]


def test_rejects_file_as_destination(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "not-a-folder"
    destination.write_text("x")
    with pytest.raises(StorageValidationError):
        validate_paths([source], destination)


def test_rejects_destination_path_through_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked-destination"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this platform")
    with pytest.raises(StorageValidationError, match="symlink or junction"):
        validate_paths([source], link / "organized")
