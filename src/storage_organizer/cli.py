from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .logging_setup import setup_logging
from .organizer import create_plan, organize
from .storage import StorageValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storage-organizer", description="Offline organizer for files on local and removable storage.")
    parser.add_argument("--version", action="version", version=f"storage-organizer {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "organize"):
        cmd = sub.add_parser(name, help="Preview organization" if name == "preview" else "Copy and organize files")
        cmd.add_argument("--source", action="append", required=True, type=Path, help="Source folder or mounted drive; repeat to add more sources")
        cmd.add_argument("--destination", required=True, type=Path, help="Destination root folder on a drive or folder")
        cmd.add_argument("--config", type=Path, help="Optional TOML configuration file")
        cmd.add_argument("--json", action="store_true", help="Print a machine-readable report")
        cmd.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preview":
            plan, config, sources, destination = create_plan(args.source, args.destination, args.config)
            if args.json:
                print(json.dumps([{"source": str(p.source), "destination": str(p.destination), "category": p.category, "action": p.action, "reason": p.reason} for p in plan], indent=2))
            else:
                print(f"Source(s): {', '.join(map(str, sources))}\nDestination: {destination}\nPlanned files: {len(plan)}")
                for item in plan:
                    print(f"[{item.action.upper()}] {item.source} -> {item.destination} ({item.reason})")
            return 0
        logger = setup_logging(verbose=args.verbose)
        def progress(done, total, item, summary):
            if not args.json:
                print(f"[{done}/{total}] {item.source.name}")
        summary, plan = organize(args.source, args.destination, args.config, progress=progress, logger=logger)
        result = {"scanned": summary.scanned, "planned": summary.planned, "copied": summary.copied, "skipped_identical": summary.skipped_identical, "failed": summary.failed, "cancelled": summary.cancelled, "errors": summary.errors}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\nOrganization complete")
            for key, value in result.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        return 130 if summary.cancelled else (1 if summary.failed else 0)
    except (StorageValidationError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
