# Testing strategy

Tests generate mock file trees at runtime with pytest's temporary-directory fixture. `scripts/create_demo_data.py` also generates a disposable manual test tree on demand. No image/video/document assets are checked into the repository. Mock files use familiar extensions to test classification but contain synthetic bytes only.

Coverage areas:

- Category mapping for photo, video, document, audio, archive, and unknown extensions.
- Recursive scan, hidden-file behavior, and symlink avoidance.
- Missing/overlapping paths and nested source deduplication.
- Dry-run leaves the destination untouched.
- Date-based folder creation and unknown-date fallback.
- Identical-content skipping, same-name/different-content renaming, and duplicate source content with the original source path recorded.
- Copy-only behavior, SHA-256 verification, and repeat-run idempotence.
- Per-file copying/copied/skipped/duplicate/error/cancelled states, unreadable-source planning errors, complete result lists, and aggregate-count consistency.
- Scan progress callbacks, monotonic byte-level transfer progress, final byte totals, zero-byte file handling, and rate-limited progress notifications.
- Deterministic depth-first scanner ordering and safe behavior when directories become inaccessible during a scan.
- Virtualized GUI result-model updates and status/search filtering (when PySide6 is installed).
- Generated large-dataset benchmark smoke test for scan, plan, bounded-memory hashing, and optional verified copying.
- Multiple-source preference persistence, recent-operation history bounds, and validated atomic GUI settings writes.
- Configuration validation and CLI JSON/text behavior.

Run locally:

```bash
python -m pip install -e ".[test]"
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

CI runs the same generated-mock-data tests on three operating systems and four supported Python versions (3.11–3.14). Tests must not read or modify user drives.

## Large-dataset benchmark

Run a disposable benchmark without touching personal drives:

```bash
python scripts/benchmark_large_dataset.py --files 10000 --file-size 4096
python scripts/benchmark_large_dataset.py --files 100000 --file-size 4096 --directories 500 --copy --json --track-memory
```

The tool reports scanner and planner throughput and optional verified-copy throughput. Add `--track-memory` to measure peak Python allocation during planning; memory instrumentation adds profiling overhead. All generated data lives in a temporary directory and is removed automatically. Compare results on the actual filesystem and storage device you intend to use; synthetic results are not a guarantee for USB, network, or removable media.
