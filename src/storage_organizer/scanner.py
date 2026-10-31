from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Iterator


def scan_files(sources: list[Path], include_hidden: bool = False) -> Iterator[Path]:
    """Yield regular files recursively; do not follow symlinks."""
    for source in sources:
        for root, dirs, filenames in os.walk(source, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(
                name for name in dirs
                if not (root_path / name).is_symlink() and (include_hidden or not name.startswith("."))
            )
            for filename in sorted(filenames):
                path = root_path / filename
                if not include_hidden and filename.startswith("."):
                    continue
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                except OSError:
                    continue
                yield path
