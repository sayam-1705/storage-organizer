"""Build and smoke-test the native PyInstaller desktop bundle."""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = ROOT / "packaging" / "entrypoints" / "gui.py"
SUPPORTED_TARGETS = ("windows", "macos", "linux")
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def project_version(root: Path = ROOT) -> str:
    """Read the package version so CI smoke builds do not drift from pyproject.toml."""
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid project version in pyproject.toml: {version!r}")
    return version


def detect_target() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"Unsupported desktop build platform: {sys.platform}")


def normalized_architecture() -> str:
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    return aliases.get(machine, machine)


def build_command(target: str, dist_path: Path, work_path: Path) -> list[str]:
    """Return a deterministic PyInstaller command for the requested target."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target {target!r}; choose one of {SUPPORTED_TARGETS}.")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "StorageOrganizer",
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(work_path),
        "--paths",
        str(ROOT / "src"),
        "--collect-all",
        "PySide6",
        "--collect-all",
        "shiboken6",
        "--collect-all",
        "PIL",
        "--collect-all",
        "pypdf",
    ]
    if target == "macos":
        command.extend(["--osx-bundle-identifier", "org.storageorganizer.desktop"])
    command.append(str(ENTRY_POINT))
    return command


def expected_bundle_path(target: str, dist_path: Path) -> Path:
    if target == "macos":
        return dist_path / "StorageOrganizer.app"
    if target == "windows":
        return dist_path / "StorageOrganizer"
    if target == "linux":
        return dist_path / "StorageOrganizer"
    raise ValueError(f"Unsupported target: {target}")


def bundle_executable(target: str, bundle_path: Path) -> Path:
    if target == "macos":
        return bundle_path / "Contents" / "MacOS" / "StorageOrganizer"
    if target == "windows":
        return bundle_path / "StorageOrganizer.exe"
    if target == "linux":
        return bundle_path / "StorageOrganizer"
    raise ValueError(f"Unsupported target: {target}")


def add_bundle_metadata(bundle_path: Path, target: str, version: str) -> None:
    metadata_root = (
        bundle_path / "Contents" / "Resources" if target == "macos" else bundle_path
    )
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "VERSION").write_text(version + "\n", encoding="utf-8")
    docs = metadata_root / "docs"
    docs.mkdir(exist_ok=True)
    for filename in ("README.md", "LICENSE", "CHANGELOG.md", "THIRD-PARTY-NOTICES.md"):
        shutil.copy2(ROOT / filename, docs / filename)


def smoke_test_bundle(target: str, bundle_path: Path) -> None:
    executable = bundle_executable(target, bundle_path)
    if not executable.is_file():
        raise FileNotFoundError(f"Frozen application executable was not created: {executable}")

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    if target == "linux":
        environment.setdefault("QT_QPA_PLATFORMTHEME", "generic")
    subprocess.run(
        [str(executable), "--smoke-test"],
        cwd=ROOT,
        env=environment,
        check=True,
        timeout=90,
    )


def build_desktop(
    target: str,
    version: str,
    *,
    root: Path = ROOT,
    run=subprocess.run,
) -> Path:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid application version: {version!r}")
    current_target = detect_target()
    if target != current_target:
        raise RuntimeError(
            f"A {target} bundle must be built on a native {target} runner; current runner is {current_target}."
        )

    architecture = normalized_architecture()
    if target == "windows" and architecture != "x86_64":
        raise RuntimeError(f"Windows packaging currently supports x86_64, not {architecture}.")
    if target == "linux" and architecture != "x86_64":
        raise RuntimeError(f"Linux AppImage packaging currently supports x86_64, not {architecture}.")
    if target == "macos" and architecture not in {"x86_64", "arm64"}:
        raise RuntimeError(f"macOS packaging does not support {architecture}.")

    dist_path = root / "dist"
    work_path = root / "build" / "pyinstaller"
    dist_path.mkdir(parents=True, exist_ok=True)
    work_path.mkdir(parents=True, exist_ok=True)

    bundle_path = expected_bundle_path(target, dist_path)
    if bundle_path.is_dir() and not bundle_path.is_symlink():
        shutil.rmtree(bundle_path)
    elif bundle_path.exists() or bundle_path.is_symlink():
        bundle_path.unlink()

    command = build_command(target, dist_path, work_path)
    run(command, cwd=root, check=True)

    if not bundle_path.exists():
        raise RuntimeError(f"PyInstaller completed but did not create {bundle_path}.")
    add_bundle_metadata(bundle_path, target, version)
    return bundle_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=SUPPORTED_TARGETS, default=detect_target())
    parser.add_argument("--version", default=project_version(), help="SemVer release version without the leading v (defaults to pyproject.toml)")
    parser.add_argument("--smoke-test", action="store_true", help="Run the frozen app's headless MainWindow smoke test")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    bundle = build_desktop(args.target, args.version)
    print(f"Built {args.target} desktop bundle: {bundle}")
    if args.smoke_test:
        smoke_test_bundle(args.target, bundle)
        print("Frozen desktop application smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
