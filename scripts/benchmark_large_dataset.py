"""Benchmark scanning, planning, and optional copying on generated synthetic files.

Examples:
    python scripts/benchmark_large_dataset.py --files 10000
    python scripts/benchmark_large_dataset.py --files 100000 --file-size 4096 --copy

All data is created inside a temporary directory and removed on exit. No user
files or mounted drives are read or modified.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from storage_organizer.config import DEFAULT_CONFIG
from storage_organizer.planner import build_plan
from storage_organizer.scanner import scan_files
from storage_organizer.transfer import execute_plan




def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Storage Organizer performance using disposable synthetic files."
    )
    parser.add_argument("--files", type=int, default=10_000, help="Number of synthetic files (default: 10000)")
    parser.add_argument("--file-size", type=int, default=4096, help="Bytes per file; minimum 8 (default: 4096)")
    parser.add_argument("--directories", type=int, default=100, help="Source subdirectories (default: 100)")
    parser.add_argument("--copy", action="store_true", help="Also benchmark the verified copy phase")
    parser.add_argument("--track-memory", action="store_true", help="Measure peak Python allocations (adds profiling overhead)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable benchmark results")
    return parser


def _create_dataset(source: Path, files: int, file_size: int, directories: int) -> None:
    payload_size = file_size - 8
    folders = [source / f"set-{index:04d}" for index in range(min(files, directories))]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    for index in range(files):
        folder = folders[index % len(folders)]
        # .bin avoids launching optional media metadata tools. This benchmark
        # isolates traversal, content hashing, and the optional verified copy.
        path = folder / f"item-{index:09d}.bin"
        with path.open("wb") as output:
            output.write(index.to_bytes(8, "big"))
            block = bytes([index % 251]) * min(1024 * 1024, payload_size)
            remaining = payload_size
            while remaining:
                chunk = block[: min(len(block), remaining)]
                output.write(chunk)
                remaining -= len(chunk)


def run_benchmark(
    files: int,
    file_size: int,
    directories: int,
    include_copy: bool,
    track_memory: bool = False,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="storage-organizer-benchmark-") as temporary:
        root = Path(temporary)
        source = root / "source"
        destination = root / "destination"
        source.mkdir()
        _create_dataset(source, files, file_size, directories)

        started = time.perf_counter()
        scanned_count = sum(1 for _ in scan_files([source]))
        scan_seconds = time.perf_counter() - started

        if track_memory:
            tracemalloc.start()
        started = time.perf_counter()
        plan = build_plan([source], destination, DEFAULT_CONFIG)
        plan_seconds = time.perf_counter() - started
        peak_bytes = None
        if track_memory:
            _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        if scanned_count != files or len(plan) != files:
            raise RuntimeError(
                f"Expected {files} files, scanner found {scanned_count}, planner produced {len(plan)}."
            )

        report = {
            "files_requested": files,
            "files_scanned": scanned_count,
            "files_planned": len(plan),
            "file_size_bytes": file_size,
            "source_bytes": files * file_size,
            "scan_seconds": round(scan_seconds, 4),
            "scan_files_per_second": round(scanned_count / scan_seconds, 2) if scan_seconds else None,
            "plan_seconds": round(plan_seconds, 4),
            "plan_files_per_second": round(len(plan) / plan_seconds, 2) if plan_seconds else None,
            "planning_peak_python_memory_bytes": peak_bytes,
            "memory_tracking_enabled": track_memory,
            "copy_requested": include_copy,
        }

        if include_copy:
            started = time.perf_counter()
            summary = execute_plan(plan)
            copy_seconds = time.perf_counter() - started
            report.update({
                "copy_seconds": round(copy_seconds, 4),
                "copied": summary.copied,
                "skipped": summary.skipped_identical,
                "failed": summary.failed,
                "copy_mib_per_second": round(
                    (summary.copied * file_size / (1024 * 1024)) / copy_seconds, 2
                ) if copy_seconds else None,
            })
            if summary.failed or summary.copied != files:
                raise RuntimeError(f"Synthetic copy benchmark did not copy every file: {report}")

        return report


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.files < 1:
        raise SystemExit("--files must be at least 1")
    if args.file_size < 8:
        raise SystemExit("--file-size must be at least 8 bytes")
    if args.directories < 1:
        raise SystemExit("--directories must be at least 1")

    report = run_benchmark(
        args.files,
        args.file_size,
        args.directories,
        args.copy,
        track_memory=args.track_memory,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Storage Organizer synthetic performance benchmark")
        print(f"Files: {report['files_scanned']:,} · File size: {args.file_size:,} bytes")
        print(
            f"Scan: {report['scan_seconds']:.3f}s "
            f"({report['scan_files_per_second']:,.0f} files/s)"
        )
        print(
            f"Plan: {report['plan_seconds']:.3f}s "
            f"({report['plan_files_per_second']:,.0f} files/s)"
        )
        if report["planning_peak_python_memory_bytes"] is not None:
            print(
                "Planning peak Python memory: "
                f"{report['planning_peak_python_memory_bytes'] / (1024 * 1024):.1f} MiB"
            )
        if args.copy:
            print(
                f"Copy: {report['copy_seconds']:.3f}s · "
                f"{report['copied']:,} copied · "
                f"{report['copy_mib_per_second']:.2f} MiB/s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
