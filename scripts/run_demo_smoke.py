"""Run a disposable end-to-end copy and repeat-run smoke test with synthetic files."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=capture)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    generator = repository / "scripts" / "create_demo_data.py"
    with tempfile.TemporaryDirectory(prefix="storage-organizer-ci-") as temp:
        root = Path(temp)
        source = root / "source"
        destination = root / "destination"
        run([sys.executable, str(generator), "--output", str(source)])
        base = [sys.executable, "-m", "storage_organizer"]
        run(base + ["preview", "--source", str(source), "--destination", str(destination)])
        first = run(base + ["organize", "--source", str(source), "--destination", str(destination), "--json"], capture=True)
        first_summary = json.loads(first.stdout)
        if first_summary["copied"] != 7 or first_summary["failed"] != 0:
            raise AssertionError(f"Unexpected first-run summary: {first_summary}")
        second = run(base + ["organize", "--source", str(source), "--destination", str(destination), "--json"], capture=True)
        second_summary = json.loads(second.stdout)
        if second_summary["copied"] != 0 or second_summary["skipped_identical"] != 7 or second_summary["failed"] != 0:
            raise AssertionError(f"Unexpected repeat-run summary: {second_summary}")
        source_files = [path for path in source.rglob("*") if path.is_file()]
        destination_files = [path for path in destination.rglob("*") if path.is_file() and not path.name.endswith(".partial")]
        if len(source_files) != 7 or len(destination_files) != 7:
            raise AssertionError(f"Expected 7 source and destination files, got {len(source_files)} and {len(destination_files)}")
        print("Synthetic end-to-end smoke test passed: 7 copied, then 7 skipped on repeat; originals preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
