from __future__ import annotations

import json
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        # Common EXIF timestamp format and ISO timestamps.
        for candidate in (text, text.replace("Z", "+00:00")):
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None
    # Keep local wall-clock dates for date-only grouping; don't silently shift zones.
    return parsed


def embedded_datetime(path: Path) -> datetime | None:
    """Read embedded dates when a supported optional reader is installed.

    This function never requires network access. Unsupported/malformed metadata is
    ignored and the caller can fall back to the filesystem modification time.
    """
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".png", ".bmp"}:
        try:
            from PIL import Image, ExifTags  # type: ignore[import-not-found]
            with Image.open(path) as image:
                exif = image.getexif()
                names = {ExifTags.TAGS.get(key, str(key)): value for key, value in exif.items()}
                # DateTimeOriginal is normally stored in the nested EXIF IFD.
                try:
                    nested = exif.get_ifd(ExifTags.IFD.Exif)
                    names.update({ExifTags.TAGS.get(key, str(key)): value for key, value in nested.items()})
                except (AttributeError, KeyError, TypeError, ValueError):
                    pass
                for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                    parsed = _parse_datetime(names.get(key))
                    if parsed:
                        return parsed
        except (ImportError, OSError, ValueError, TypeError):
            pass
    if suffix == ".pdf":
        try:
            with path.open("rb") as signature_stream:
                if signature_stream.read(5) != b"%PDF-":
                    return None
            from pypdf import PdfReader  # type: ignore[import-not-found]
            with path.open("rb") as stream:
                metadata = PdfReader(stream).metadata
                if metadata:
                    for key in ("/CreationDate", "/ModDate"):
                        raw = metadata.get(key)
                        if raw:
                            # PDF dates often use D:YYYYMMDDHHmmSS; normalize common form.
                            text = str(raw)
                            if text.startswith("D:") and len(text) >= 10:
                                parsed = _parse_datetime(f"{text[2:6]}-{text[6:8]}-{text[8:10]} {text[10:12] or '00'}:{text[12:14] or '00'}:{text[14:16] or '00'}")
                                if parsed:
                                    return parsed
        except Exception:
            # Optional metadata readers can raise format-specific exceptions for corrupt or mock files.
            pass
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                xml = ElementTree.fromstring(archive.read("docProps/core.xml"))
            for node in xml.iter():
                if node.tag.endswith("}created") or node.tag.endswith("}modified"):
                    parsed = _parse_datetime(node.text)
                    if parsed:
                        return parsed
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError, ValueError):
            pass
    if suffix in {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".m4a", ".flac", ".wav", ".ogg"}:
        # ffprobe is optional. Ask for format creation_time without shell invocation.
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_entries", "format_tags=creation_time", str(path)],
                capture_output=True, text=True, timeout=8, check=False,
            )
            if result.returncode == 0:
                tags = json.loads(result.stdout).get("format", {}).get("tags", {})
                for key, value in tags.items():
                    if key.lower() == "creation_time":
                        parsed = _parse_datetime(value)
                        if parsed:
                            return parsed
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
            pass
    return None


def resolve_datetime(path: Path, policy: str = "metadata_then_modified") -> datetime | None:
    if policy == "modified":
        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None
    embedded = embedded_datetime(path)
    if embedded:
        return embedded
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None
