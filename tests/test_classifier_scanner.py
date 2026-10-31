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


def test_scanner_preserves_deterministic_depth_first_order(tmp_path, make_file):
    source = tmp_path / "source"
    make_file(source / "z-root.txt", b"z")
    make_file(source / "a-root.txt", b"a")
    make_file(source / "z-folder" / "z-file.txt", b"z")
    make_file(source / "a-folder" / "b-file.txt", b"b")
    make_file(source / "a-folder" / "a-file.txt", b"a")

    found = [path.relative_to(source).as_posix() for path in scan_files([source])]

    assert found == [
        "a-root.txt",
        "z-root.txt",
        "a-folder/a-file.txt",
        "a-folder/b-file.txt",
        "z-folder/z-file.txt",
    ]


def test_scanner_handles_unreadable_or_disappearing_directory(tmp_path, monkeypatch):
    import storage_organizer.scanner as scanner

    source = tmp_path / "source"
    source.mkdir()
    real_scandir = scanner.os.scandir

    def selective_scandir(path):
        if Path(path) == source:
            raise PermissionError("simulated directory access failure")
        return real_scandir(path)

    monkeypatch.setattr(scanner.os, "scandir", selective_scandir)
    assert list(scan_files([source])) == []
