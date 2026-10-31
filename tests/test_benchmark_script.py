from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_large_dataset_benchmark_smoke(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    script = repository / "scripts" / "benchmark_large_dataset.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--files", "40",
            "--file-size", "128",
            "--directories", "4",
            "--copy",
            "--track-memory",
            "--json",
        ],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    )
    import json

    report = json.loads(result.stdout)
    assert report["files_scanned"] == 40
    assert report["files_planned"] == 40
    assert report["copied"] == 40
    assert report["failed"] == 0
    assert report["scan_seconds"] >= 0
    assert report["plan_seconds"] >= 0
    assert report["planning_peak_python_memory_bytes"] > 0


def test_benchmark_resolves_symlinked_temporary_directory(tmp_path, monkeypatch):
    """A macOS-style /var -> /private/var temp alias must not break safe copies."""
    import shutil
    from scripts import benchmark_large_dataset as benchmark

    physical_parent = tmp_path / "physical-temp"
    alias_parent = tmp_path / "temp-alias"
    physical_parent.mkdir()
    try:
        alias_parent.symlink_to(physical_parent, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest
        pytest.skip(f"Symlink creation is not permitted: {exc}")

    class SymlinkedTemporaryDirectory:
        def __init__(self, prefix):
            self.physical = physical_parent / f"{prefix}test"
            self.alias = alias_parent / self.physical.name

        def __enter__(self):
            self.physical.mkdir()
            return str(self.alias)

        def __exit__(self, exc_type, exc_value, traceback):
            shutil.rmtree(self.physical, ignore_errors=True)
            return False

    monkeypatch.setattr(benchmark.tempfile, "TemporaryDirectory", SymlinkedTemporaryDirectory)
    report = benchmark.run_benchmark(
        files=4, file_size=32, directories=2, include_copy=True
    )

    assert report["copied"] == 4
    assert report["failed"] == 0
