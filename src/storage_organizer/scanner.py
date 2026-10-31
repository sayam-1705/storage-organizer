from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path


def scan_files(sources: list[Path], include_hidden: bool = False) -> Iterator[Path]:
    """Yield regular files deterministically without following symlinks.

    ``os.scandir`` exposes cached directory-entry type information on common
    filesystems. Using ``DirEntry.is_file/is_dir(follow_symlinks=False)`` avoids
    the separate ``Path.is_symlink`` and ``Path.is_file`` metadata calls that
    otherwise occur for every file. Directories are traversed depth-first in
    lexical order, and files in each directory are yielded before child folders,
    matching the previous ``os.walk`` ordering contract.
    """
    for source in sources:
        pending_directories = [source]
        while pending_directories:
            directory = pending_directories.pop()
            try:
                with os.scandir(directory) as iterator:
                    entries = sorted(iterator, key=lambda entry: entry.name)
            except OSError:
                # os.walk's default onerror=None behavior also skips unreadable
                # directories rather than aborting an entire drive scan.
                continue

            child_directories: list[str] = []
            for entry in entries:
                if not include_hidden and entry.name.startswith("."):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        child_directories.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        yield Path(entry.path)
                except OSError:
                    # A removable drive may change while it is being scanned.
                    # Ignore entries that disappear or become inaccessible.
                    continue

            # A stack is used instead of Python recursion so deeply nested
            # directory trees cannot exhaust the interpreter recursion limit.
            pending_directories.extend(reversed(child_directories))
