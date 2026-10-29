# Architecture

## Design

The application has two entry points (CLI and optional PySide6 GUI) and one shared core. The core scans selected paths, classifies files, resolves a date, builds a preview plan, hashes existing destination files, then copies and verifies files. It has no database layer or network client.

## Modules

- `storage.py`: path normalization, source/destination overlap validation, symlink/junction checks, free-space helper.
- `scanner.py`: recursive traversal without following symlinks; hidden files are configurable.
- `classifier.py`: extension-to-category mapping.
- `metadata.py`: optional local metadata extraction and filesystem timestamp fallback.
- `planner.py`: destination layout, cross-platform filename normalization, and conflict/duplicate planning.
- `hashing.py`: bounded-memory SHA-256.
- `transfer.py`: temp-file copy, verification, no-overwrite publishing, summaries.
- `config.py`: TOML config and platform-specific user config directory.
- `logging_setup.py`: rotating local log.
- `preferences.py`: atomic JSON persistence for last GUI paths; no database.
- `cli.py`, `gui.py`: interfaces only; no duplicated organization logic.

## Transfer protocol

1. Validate source/destination paths and reject overlap.
2. Scan source files without following symlinks.
3. Hash source files and any existing destination files.
4. Create a plan; no destination directories are created during preview.
5. For each copy, revalidate the source and destination path, create the destination directory, and write to a temporary file in that directory.
6. Verify the temporary copy, publish with no-overwrite semantics (atomic where the OS supports it), and verify the published file.
7. Sync the destination directory where supported, log the outcome, and leave the source unchanged.

## Persistence

TOML preferences and rotating text logs are used instead of a database. The destination is rescanned on each run, so a database is not needed for duplicate detection. Operation reports can be redirected by the caller; no file-content index is maintained.
