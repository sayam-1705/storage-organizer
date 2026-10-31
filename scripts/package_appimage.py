"""Assemble a PyInstaller desktop bundle into an x86_64 AppImage."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
APP_NAME = "Storage Organizer"
ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
<rect x="20" y="20" width="216" height="216" rx="42" fill="#2457A7"/>
<path d="M70 82h116v24H70zm0 44h116v24H70zm0 44h76v24H70z" fill="#fff"/>
<path d="M166 166l18 18 31-36" fill="none" stroke="#69D1B2" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>
</svg>\n'''


def prepare_appdir(distribution: Path, appdir: Path) -> Path:
    executable = distribution / "StorageOrganizer"
    if not distribution.is_dir() or not executable.is_file():
        raise FileNotFoundError(
            f"Expected a PyInstaller onedir bundle containing {executable}."
        )

    resolved_distribution = distribution.resolve()
    resolved_appdir = appdir.resolve()
    if (
        resolved_distribution == resolved_appdir
        or resolved_distribution in resolved_appdir.parents
        or resolved_appdir in resolved_distribution.parents
    ):
        raise ValueError("AppDir must not overlap the PyInstaller distribution directory.")

    if appdir.exists() or appdir.is_symlink():
        if appdir.is_symlink() or not appdir.is_dir():
            appdir.unlink()
        else:
            shutil.rmtree(appdir)
    binary_dir = appdir / "usr" / "bin"
    icon_dir = appdir / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    binary_dir.mkdir(parents=True)
    icon_dir.mkdir(parents=True)
    shutil.copytree(distribution, binary_dir / "StorageOrganizer")

    (appdir / "AppRun").write_text(
        '#!/bin/sh\nset -eu\nexec "${APPDIR}/usr/bin/StorageOrganizer/StorageOrganizer" "$@"\n',
        encoding="utf-8",
    )
    (appdir / "AppRun").chmod(0o755)

    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Storage Organizer\n"
        "Comment=Offline organizer for local and removable storage\n"
        "Exec=AppRun\n"
        "TryExec=AppRun\n"
        "Icon=storage-organizer\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=true\n"
    )
    (appdir / "storage-organizer.desktop").write_text(desktop, encoding="utf-8")
    (appdir / "storage-organizer.svg").write_text(ICON_SVG, encoding="utf-8")
    shutil.copy2(appdir / "storage-organizer.svg", icon_dir / "storage-organizer.svg")
    shutil.copy2(appdir / "storage-organizer.svg", appdir / ".DirIcon")

    docs = appdir / "usr" / "share" / "doc" / "storage-organizer"
    docs.mkdir(parents=True)
    for filename in ("README.md", "LICENSE", "CHANGELOG.md", "THIRD-PARTY-NOTICES.md"):
        shutil.copy2(ROOT / filename, docs / filename)
    return appdir


def build_appimage(
    distribution: Path,
    appdir: Path,
    appimagetool: Path,
    output: Path,
    version: str,
    *,
    run=subprocess.run,
    smoke_test: bool = True,
) -> Path:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid application version: {version!r}")
    if not appimagetool.is_file():
        raise FileNotFoundError(f"AppImage tool not found: {appimagetool}")

    prepare_appdir(distribution, appdir)
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["VERSION"] = version
    environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    run(
        [str(appimagetool), str(appdir), str(output)],
        cwd=ROOT,
        env=environment,
        check=True,
        timeout=300,
    )
    if not output.is_file():
        raise RuntimeError(f"AppImage tool completed but did not create {output}.")
    output.chmod(output.stat().st_mode | 0o111)

    if smoke_test:
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.setdefault("QT_QPA_PLATFORMTHEME", "generic")
        run(
            [str(output), "--smoke-test"],
            cwd=ROOT,
            env=environment,
            check=True,
            timeout=90,
        )
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--distribution", type=Path, default=ROOT / "dist" / "StorageOrganizer")
    parser.add_argument("--appdir", type=Path, default=ROOT / "build" / "StorageOrganizer.AppDir")
    parser.add_argument("--appimagetool", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-smoke-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output or (
        ROOT / "release-assets" / f"StorageOrganizer-{args.version}-linux-x86_64.AppImage"
    )
    result = build_appimage(
        args.distribution,
        args.appdir,
        args.appimagetool,
        output,
        args.version,
        smoke_test=not args.skip_smoke_test,
    )
    print(f"Built AppImage: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
