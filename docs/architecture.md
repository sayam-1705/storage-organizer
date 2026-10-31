# Architecture

## Design

The application has two entry points (CLI and optional PySide6 GUI) and one shared core. The core scans selected paths, classifies files, resolves a date, builds a preview plan, hashes existing destination files, then copies and verifies files. It has no database layer or network client.

## Modules

- `storage.py`: path normalization, source/destination overlap validation, symlink/junction checks, free-space helper.
- `scanner.py`: deterministic `os.scandir` traversal without following symlinks; cached directory-entry type information avoids redundant per-file metadata calls, and hidden files are configurable.
- `classifier.py`: extension-to-category mapping.
- `metadata.py`: optional local metadata extraction and filesystem timestamp fallback.
- `planner.py`: destination layout, cross-platform filename normalization, conflict planning, and explicit destination-skip versus source-duplicate classification.
- `hashing.py`: bounded-memory SHA-256.
- `transfer.py`: temp-file copy, verification, no-overwrite publishing, structured per-file outcomes, byte-level transfer progress, and aggregate summaries.
- `config.py`: TOML config, validated atomic settings writes, and platform-specific user config directory.
- `logging_setup.py`: rotating local log.
- `preferences.py`: atomic JSON persistence for multiple GUI source paths and the bounded recent-operation history; no database.
- `cli.py`, `gui.py`: interfaces only; no duplicated organization logic. The GUI uses a virtualized Qt result model and proxy filters rather than creating a Qt item for every cell, and batches/rate-limits progress updates for large collections.

## Transfer protocol

1. Validate source/destination paths and reject overlap.
2. Scan source files without following symlinks.
3. Hash source files and any existing destination files.
4. Create a plan; no destination directories are created during preview.
5. For each copy, revalidate the source and destination path, create the destination directory, and write to a temporary file in that directory.
6. Verify the temporary copy, publish with no-overwrite semantics (atomic where the OS supports it), and verify the published file.
7. Sync the destination directory where supported, log the outcome, and leave the source unchanged.
8. Retain one result per discovered file. Copies, destination skips, source duplicates, errors, and files not started after cancellation have distinct terminal statuses and explanatory details.

## Persistence

TOML settings, JSON preferences/history, and rotating text logs are used instead of a database. The GUI stores up to 10 recent operation summaries, including the selected paths and aggregate results; it does not persist file contents or a file index. The destination is rescanned on each run, so a database is not needed for duplicate detection. Operation reports can be redirected by the caller; no file-content index is maintained.
