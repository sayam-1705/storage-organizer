# Storage Organizer

An offline, cross-platform utility that copies files from user-selected physical storage (external HDDs/SSDs, USB drives, or folders) into a category/year/month directory structure. It provides a CLI and an optional PySide6 desktop GUI. It does not require a database, cloud service, account, or internet connection at runtime.

## Download

Storage Organizer is distributed through GitHub Releases. No PyPI
publication is required.

**Latest stable release:** [Download Storage Organizer](https://github.com/sayam-1705/storage-organizer/releases/latest)

The release includes:

- **Python wheel:** Recommended for installation.
- **Source distribution:** For inspecting or rebuilding the package.

Requirements: Python 3.11 or newer.

For installation instructions, see [Install a Released Version](#install-a-released-version).

## Safety defaults

- **Copy-only:** original source files are never deleted.
- **Preview first:** `preview` calculates the plan without creating the destination or copying files.
- **No silent overwrites:** identical content is skipped; name conflicts are renamed.
- **Verification:** copies are checked with SHA-256 by default.
- **No overlapping source/destination:** paths are validated to prevent recursive self-processing.
- **Symlink-aware writes:** destination symlinks/junctions and non-portable filename conflicts are guarded against.
- **Offline:** optional metadata tools are local programs/libraries; no network calls are made.

## Requirements

- Python 3.11 or newer.
- Optional GUI: PySide6.
- Optional richer metadata extraction: Pillow, pypdf, and/or `ffprobe` from FFmpeg. Missing optional metadata tools simply cause the organizer to fall back to the file's modification timestamp.


## Install a Released Version

Download the latest stable version from the
[GitHub Releases page](https://github.com/sayam-1705/storage-organizer/releases/latest).

### CLI installation

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the v1.0.1 wheel directly from GitHub:

```bash
python -m pip install --upgrade pip
python -m pip install "storage-organizer @ https://github.com/sayam-1705/storage-organizer/releases/download/v1.0.1/storage_organizer-1.0.1-py3-none-any.whl"
```

Verify the installation:

```bash
storage-organizer --version
storage-organizer --help
```

### Desktop GUI and optional media support

To install the GUI and optional media metadata dependencies:

```bash
python -m pip install "storage-organizer[gui,media] @ https://github.com/sayam-1705/storage-organizer/releases/download/v1.0.1/storage_organizer-1.0.1-py3-none-any.whl"
```

Launch the desktop application:

```bash
storage-organizer-gui
```

The GUI requires PySide6. On Linux, native Qt system libraries may also be required. Optional media support uses Pillow and pypdf; `ffprobe` must be installed separately if you want to use it.

### Development installation

For contributors working from a local clone:

```bash
git clone https://github.com/sayam-1705/storage-organizer.git
cd storage-organizer

python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[test,gui,media]"
```

To run the tests:

```bash
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

Released package files are hosted on GitHub. Python dependencies
may be downloaded from your configured package index during installation.

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

The GUI supports adding multiple source drives/folders, removing selected sources, and choosing a destination. It shows scan progress, a per-file results table, transfer throughput, and an estimated time remaining while copying. Search and status filters help narrow large result lists. The **Settings** dialog controls hidden-file scanning, date selection policy, and the unknown-date folder; SHA-256 verification remains enabled. The **Recent activity** tab keeps the last 10 operation summaries locally. Cancellation is honored between files, and original source files remain untouched. A destination path can be typed even if the final folder does not exist yet. A missing PySide6 dependency produces an installation hint.

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

## Duplicate behavior and per-file results

The organizer calculates SHA-256 hashes using bounded-memory streaming. If identical content already exists anywhere in the destination, the file is reported as **Skipped** and the existing destination path is included in the result. If identical content appears more than once in the selected source set, the first file is copied and each later match is reported as **Duplicate**, with the original source path identified. If two different files would otherwise have the same destination filename, a suffix such as `report (1).pdf` is used. A new run re-scans the destination and can safely skip content copied in a previous run.

Every discovered file receives a result with its source, planned destination, final status, reason, SHA-256 digest when readable, and duplicate reference where applicable. A file that cannot be read during planning is retained as an `error` result without preventing other files from proceeding. Final statuses are `copied`, `skipped`, `duplicate`, `error`, and `cancelled`; `copying` is also emitted as a live GUI/worker state. Cancellation marks every file that was not started as `cancelled` rather than leaving it without a result.

The `organize --json` report includes aggregate counts and a `files` array containing the individual outcomes. The desktop GUI displays the same information in a per-file results table.

## Configuration and logs

Copy `config.example.toml` to a local config file and pass it with `--config`. By default, user settings/logs are kept in the operating system's application configuration area (for example, `~/.config/storage-organizer/` on Linux). The app writes a rotating `organizer.log`, a `preferences.json` file for the GUI's selected source/destination paths, and a `recent-runs.json` file containing the last 10 operation summaries. The history contains local paths and aggregate counts, but no file contents. The app does not create a database. Keep personal settings, history, and logs out of source control.

## Tests and mock data

Tests generate all sample files dynamically in pytest temporary directories. For a manual smoke test, generate disposable synthetic files with `python scripts/create_demo_data.py --output /tmp/storage-organizer-demo/source` (choose any writable path on your OS), then preview into a different destination folder. There are **no real images, videos, documents, or personal files committed as fixtures**. Mock `.jpg`/`.pdf` files contain only test bytes and exist only in temporary test directories. Run:

```bash
python -m pip install -e ".[test]"
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

CI runs these tests on Windows, macOS, and Ubuntu for Python 3.11, 3.12, 3.13, and 3.14, then smoke-tests the CLI and headless GUI initialization. The tests exercise classification, deterministic recursive scanning, path safety, dry-run, category/date routing, destination skips versus source duplicates, per-file success/error/cancellation outcomes, scan/transfer progress, filename conflicts, copy verification, repeat runs, configuration validation, preference/history persistence, and CLI JSON results.

For large synthetic workloads, run `python scripts/benchmark_large_dataset.py --files 10000 --file-size 4096`. Add `--copy` to include verified transfer throughput, `--track-memory` to sample planning allocations (with profiling overhead), or `--json` for machine-readable results. The benchmark creates and removes its own temporary dataset; it does not read real source drives.

## Production-readiness checklist

See [docs/production-readiness.md](docs/production-readiness.md) for the release checklist, safeguards, and remaining platform/filesystem limitations. CI tests Windows, macOS, and Ubuntu across Python 3.11, 3.12, 3.13, and 3.14. It runs unit and integration tests, CLI and synthetic end-to-end smoke tests, headless Qt GUI initialization, source compilation, distribution builds, dependency consistency checks, and a guard against tracked media or binary fixtures.

## Known limitations

- Metadata coverage varies by file type and optional tools. The fallback is modification time, not a guaranteed original creation date.
- FAT32 cannot store individual files larger than 4 GB; copying such files fails safely and is reported.
- The first release is copy-only; it never deletes source files.
- A file-based log is not a transactional journal. After a crash, rerun the operation; destination hashes are rechecked and identical content is skipped.
- Filesystems differ in filename rules and metadata support. Test with a small sample before processing a large drive.

## License

MIT. See [LICENSE](LICENSE).
