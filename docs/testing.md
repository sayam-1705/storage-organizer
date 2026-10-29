# Testing strategy

Tests generate mock file trees at runtime with pytest's temporary-directory fixture. `scripts/create_demo_data.py` also generates a disposable manual test tree on demand. No image/video/document assets are checked into the repository. Mock files use familiar extensions to test classification but contain synthetic bytes only.

Coverage areas:

- Category mapping for photo, video, document, audio, archive, and unknown extensions.
- Recursive scan, hidden-file behavior, and symlink avoidance.
- Missing/overlapping paths and nested source deduplication.
- Dry-run leaves the destination untouched.
- Date-based folder creation and unknown-date fallback.
- Identical-content skipping, same-name/different-content renaming, and duplicate source content.
- Copy-only behavior, SHA-256 verification, and repeat-run idempotence.
- Configuration validation and CLI JSON/text behavior.

Run locally:

```bash
python -m pip install -e ".[test]"
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

CI runs the same generated-mock-data tests on three operating systems and three supported Python versions. Tests must not read or modify user drives.
