from pathlib import Path
from storage_organizer.classifier import classify
from storage_organizer.scanner import scan_files


def test_classifies_common_extensions():
    assert classify(Path("image.JPEG")) == "Photos"
    assert classify(Path("clip.mp4")) == "Videos"
    assert classify(Path("notes.pdf")) == "Documents"
    assert classify(Path("song.flac")) == "Audio"
    assert classify(Path("backup.zip")) == "Archives"
    assert classify(Path("mystery.bin")) == "Other"


def test_scanner_recurses_and_skips_hidden_by_default(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "nested" / "ok.txt")
    make_file(source / ".hidden" / "secret.txt")
    make_file(source / ".hidden-file.txt")
    found = list(scan_files([source]))
    assert [p.name for p in found] == ["ok.txt"]
    found_with_hidden = list(scan_files([source], include_hidden=True))
    assert len(found_with_hidden) == 3


def test_scanner_does_not_follow_symlinked_directories(tmp_path, make_file):
    source = tmp_path / "source"
    outside = tmp_path / "outside"
    make_file(outside / "private.txt")
    source.mkdir()
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    assert list(scan_files([source])) == []
