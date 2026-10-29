# Storage Organizer

An offline, cross-platform utility that copies files from user-selected physical storage (external HDDs/SSDs, USB drives, or folders) into a category/year/month directory structure. It provides a CLI and an optional PySide6 desktop GUI. It does not require a database, cloud service, account, or internet connection at runtime.

## Safety defaults

- **Copy-only:** original source files are never deleted.
- **Preview first:** `preview` calculates the plan without creating the destination or copying files.
- **No silent overwrites:** identical content is skipped; name conflicts are renamed.
- **Verification:** copies are checked with SHA-256 by default.
- **No overlapping source/destination:** paths are validated to prevent recursive self-processing.
- **Offline:** optional metadata tools are local programs/libraries; no network calls are made.

## Requirements

- Python 3.11 or newer.
- Optional GUI: PySide6.
- Optional richer metadata extraction: Pillow, pypdf, and/or `ffprobe` from FFmpeg. Missing optional metadata tools simply cause the organizer to fall back to the file's modification timestamp.

## Install

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test,gui,media]"
```

If you only need the CLI, use `python -m pip install -e ".[test]"`. Run without installation using `PYTHONPATH=src python -m storage_organizer --help` (PowerShell: `$env:PYTHONPATH='src'; python -m storage_organizer --help`).

## CLI usage

```bash
# Preview without modifying files
storage-organizer preview --source "/media/user/ExternalDrive" --destination "/media/user/USB/OrganizedStorage"

# Copy and verify
storage-organizer organize --source "/media/user/ExternalDrive" --destination "/media/user/USB/OrganizedStorage"

# Multiple source folders/drives
storage-organizer preview --source "/media/user/DriveA" --source "/media/user/DriveB" --destination "/media/user/USB/OrganizedStorage"

# Machine-readable output
storage-organizer organize --source "/media/user/ExternalDrive" --destination "/media/user/USB/OrganizedStorage" --json

# Optional custom config
storage-organizer preview --source ./input --destination ./output --config ./config.example.toml
```

Use the actual mount point or drive path for your operating system. On Windows, examples may look like `E:\\` and `F:\\OrganizedStorage`; quote paths containing spaces. The application does not automatically mount drives or bypass OS permissions.

## GUI usage

After installing the GUI extra:

```bash
storage-organizer-gui
# or
python -m storage_organizer.gui
```

The GUI allows choosing a source drive/folder and destination path, previewing the plan, running a copy, and requesting cancellation between files. A destination path can be typed even if the final folder does not exist yet. The current GUI selects one source at a time; the CLI supports multiple `--source` arguments. A missing PySide6 dependency produces an installation hint.

## Folder structure

```text
OrganizedStorage/
├── Photos/2025/March/
├── Videos/2026/October/
├── Documents/2026/October/
├── Audio/2026/October/
├── Archives/2026/October/
└── Other/2026/October/
```

Files with no resolvable timestamp go into `<Category>/UnknownDate/`. Category is determined by extension. Embedded metadata is read only when supported by an installed optional tool; otherwise modification time is used. Supported embedded metadata includes common image EXIF dates, PDF dates (with pypdf), DOCX core properties, and media creation timestamps when `ffprobe` is installed.

## Duplicate behavior

The organizer calculates SHA-256 hashes using bounded-memory streaming. If identical content already exists anywhere in the destination, it is skipped. If two different files would otherwise have the same destination filename, a suffix such as `report (1).pdf` is used. Identical contents among the current source set are copied once. A new run re-scans the destination and can safely skip content already copied in a previous run.

## Configuration and logs

Copy `config.example.toml` to a local config file and pass it with `--config`. By default, user settings/logs are kept in the operating system's application configuration area (for example, `~/.config/storage-organizer/` on Linux). The app writes a rotating `organizer.log` and a small `preferences.json` file for the GUI’s last source/destination selections; it does not create a database. Keep personal logs out of source control.

## Tests and mock data

Tests generate all sample files dynamically in pytest temporary directories. For a manual smoke test, generate disposable synthetic files with `python scripts/create_demo_data.py --output /tmp/storage-organizer-demo/source` (choose any writable path on your OS), then preview into a different destination folder. There are **no real images, videos, documents, or personal files committed as fixtures**. Mock `.jpg`/`.pdf` files contain only test bytes and exist only in temporary test directories. Run:

```bash
python -m pip install -e ".[test]"
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

CI runs these tests on Windows, macOS, and Ubuntu for Python 3.11, 3.12, and 3.13, then smoke-tests the CLI. The tests exercise classification, recursive scanning, path safety, dry-run, category/date routing, duplicates, filename conflicts, copy verification, repeat runs, configuration validation, and CLI output.

## Known limitations

- Metadata coverage varies by file type and optional tools. The fallback is modification time, not a guaranteed original creation date.
- FAT32 cannot store individual files larger than 4 GB; copying such files fails safely and is reported.
- The first release is copy-only; it never deletes source files.
- GUI source selection currently chooses one folder/drive per run; use repeated `--source` options in the CLI for multiple sources.
- A file-based log is not a transactional journal. After a crash, rerun the operation; destination hashes are rechecked and identical content is skipped.
- Filesystems differ in filename rules and metadata support. Test with a small sample before processing a large drive.

## License

MIT. See [LICENSE](LICENSE).
