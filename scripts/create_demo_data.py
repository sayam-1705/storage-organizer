"""Create a disposable synthetic source tree for manual testing (no real media assets)."""
from __future__ import annotations
import argparse
import os
from datetime import datetime
from pathlib import Path

SAMPLES = {
    "Phone/DCIM/IMG_2025.jpg": b"SYNTHETIC TEST FILE - not a real JPEG image\nmock-photo-2025",
    "Phone/DCIM/IMG_2026.png": b"SYNTHETIC TEST FILE - not a real PNG image\nmock-photo-2026",
    "Phone/Camera/clip.mp4": b"SYNTHETIC TEST FILE - not a real MP4 video\nmock-video",
    "College/assignment.pdf": b"SYNTHETIC TEST FILE - not a real PDF document\nmock-document",
    "Downloads/notes.txt": b"Synthetic test document for Storage Organizer.\n",
    "Downloads/archive.zip": b"SYNTHETIC TEST FILE - not a real ZIP archive\nmock-archive",
    "Downloads/unknown.bin": b"Synthetic unknown extension.\n",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory where disposable mock files will be created")
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dates = {
        "IMG_2025.jpg": datetime(2025, 3, 14, 12).timestamp(),
        "IMG_2026.png": datetime(2026, 10, 5, 12).timestamp(),
        "clip.mp4": datetime(2026, 9, 20, 12).timestamp(),
        "assignment.pdf": datetime(2025, 11, 7, 12).timestamp(),
        "notes.txt": datetime(2026, 10, 29, 12).timestamp(),
        "archive.zip": datetime(2026, 1, 2, 12).timestamp(),
        "unknown.bin": datetime(2024, 6, 3, 12).timestamp(),
    }
    for relative, content in SAMPLES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        stamp = dates[path.name]
        os.utime(path, (stamp, stamp))
    print(f"Created {len(SAMPLES)} synthetic files under {root}")
    print("These files use media-like extensions for testing but are not real images, videos, PDFs, or archives.")
    print("Preview with: storage-organizer preview --source <source> --destination <separate-destination>")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
