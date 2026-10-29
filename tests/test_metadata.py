from __future__ import annotations

from datetime import datetime
import zipfile

from storage_organizer.metadata import _parse_datetime, embedded_datetime, resolve_datetime


def test_parse_exif_and_iso_dates():
    assert _parse_datetime("2025:03:14 12:30:00") == datetime(2025, 3, 14, 12, 30, 0)
    assert _parse_datetime("2026-10-29T08:15:00") == datetime(2026, 10, 29, 8, 15, 0)
    assert _parse_datetime("not a date") is None
    assert _parse_datetime(None) is None


def test_docx_core_metadata_is_read_without_extraction(tmp_path):
    path = tmp_path / "sample.docx"
    core_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
      xmlns:dcterms="http://purl.org/dc/terms/">
      <dcterms:created>2021-04-05T10:11:12Z</dcterms:created>
    </cp:coreProperties>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("docProps/core.xml", core_xml)
    result = embedded_datetime(path)
    assert result is not None
    assert result.replace(tzinfo=None) == datetime(2021, 4, 5, 10, 11, 12)


def test_corrupt_supported_format_falls_back_to_filesystem_time(tmp_path, make_file):
    path = make_file(tmp_path / "corrupt.jpg", b"not an image", datetime(2024, 6, 3, 12, 0, 0))
    assert embedded_datetime(path) is None
    assert resolve_datetime(path, "metadata_then_modified").year == 2024


def test_modified_policy_does_not_need_embedded_metadata(tmp_path, make_file, monkeypatch):
    import storage_organizer.metadata as metadata
    path = make_file(tmp_path / "notes.txt", b"notes", datetime(2022, 7, 8, 9, 10, 11))
    monkeypatch.setattr(metadata, "embedded_datetime", lambda _path: (_ for _ in ()).throw(AssertionError("must not read metadata")))
    assert resolve_datetime(path, "modified").year == 2022
