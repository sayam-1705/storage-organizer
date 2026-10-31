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
