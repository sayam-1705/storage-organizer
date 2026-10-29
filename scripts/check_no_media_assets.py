"""Fail CI if binary media assets are tracked in Git. Mock files are generated in temp dirs."""
from __future__ import annotations
import subprocess
import sys
from pathlib import PurePosixPath

FORBIDDEN = {
    ".jpg", ".jpeg", ".jfif", ".png", ".gif", ".webp", ".avif", ".jxl", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".svg", ".ico", ".icns", ".psd", ".xcf",
    ".raw", ".dng", ".cr2", ".nef", ".arw", ".orf", ".rw2", ".jpe", ".jp2", ".apng", ".tga", ".ppm", ".pgm", ".pbm",
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".mpeg", ".mpg", ".3gp", ".mts", ".m2ts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff",
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz",
}


def main() -> int:
    try:
        result = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Unable to inspect tracked files: {exc}", file=sys.stderr)
        return 2
    tracked = [PurePosixPath(item.decode("utf-8", errors="replace")) for item in result.stdout.split(b"\0") if item]
    forbidden = [str(path) for path in tracked if path.suffix.lower() in FORBIDDEN]
    if forbidden:
        print("Media/document/archive assets must not be committed:", file=sys.stderr)
        print("\n".join(forbidden), file=sys.stderr)
        return 1
    print("No media/document/archive assets are tracked in Git.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
