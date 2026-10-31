## Unreleased

- Added structured per-file operation results across planning, transfers, CLI JSON output, and the desktop GUI.
- Distinguished files already present in the destination from duplicates within the selected source set.
- Added explicit per-file cancellation and error outcomes, plus deterministic source traversal.
- Added multi-folder GUI source management, scan and byte-transfer progress with throughput/ETA, and file-result search/status filters.
- Added a GUI settings dialog with validated atomic configuration saving and a local history of the 10 latest operations.
- Added a deterministic `os.scandir` traversal path that reduces repeated filesystem metadata calls during large scans.
- Replaced the current-operation `QTableWidget` with a virtualized Qt table model and proxy filtering for large result sets.
- Batched per-file GUI updates and rate-limited byte-progress notifications to reduce GUI event-queue pressure.
- Added a disposable large-dataset benchmark for scan, plan, memory, and optional verified-copy throughput.

# Changelog

## 1.0.1 — Production-readiness hardening

- Reject unsafe date-fallback folder names, invalid rename templates, unknown configuration sections, and unknown configuration keys.
- Detect destination symlinks/junctions before planning and recheck destination paths before writing.
- Recheck source file type immediately before copying and avoid deleting a destination file after a verification mismatch.
- Add no-overwrite atomic publication paths for Windows, Linux, and macOS where supported, with a guarded fallback for unusual platforms/filesystems.
- Ignore stale temporary partial files during duplicate detection so a crash cannot make a temporary artifact look like a completed copy.
- Normalize non-portable filenames and improve collision matching for case/Unicode-insensitive filesystems.
- Set Qt's generic platform theme by default on Linux to avoid a known GNOME xsettings schema startup crash; explicit user overrides are respected.
- Expand tests, add GUI smoke checks to cross-platform CI, test package builds, and broaden the tracked-media guard.
