from __future__ import annotations

import os
from pathlib import Path
import tomllib

import pytest

from scripts import build_desktop, package_appimage


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("windows", "StorageOrganizer"),
        ("macos", "StorageOrganizer.app"),
        ("linux", "StorageOrganizer"),
    ],
)
def test_pyinstaller_command_is_native_and_collects_qt(target, expected, tmp_path):
    command = build_desktop.build_command(target, tmp_path / "dist", tmp_path / "work")
    assert "--onedir" in command
    assert "--windowed" in command
    assert "--collect-all" in command
    assert command.count("PySide6") == 1
    assert command.count("shiboken6") == 1
    assert command.count("PIL") == 1
    assert command.count("pypdf") == 1
    assert command[-1].replace("\\", "/").endswith("packaging/entrypoints/gui.py")
    assert build_desktop.expected_bundle_path(target, tmp_path / "dist").name == expected
    if target == "macos":
        assert "--osx-bundle-identifier" in command


def test_build_desktop_rejects_cross_platform_builds(monkeypatch, tmp_path):
    monkeypatch.setattr(build_desktop, "detect_target", lambda: "linux")
    with pytest.raises(RuntimeError, match="native windows runner"):
        build_desktop.build_desktop("windows", "1.0.1", root=tmp_path)


def test_build_desktop_validates_version_before_running(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(build_desktop, "detect_target", lambda: "linux")
    with pytest.raises(ValueError, match="Invalid application version"):
        build_desktop.build_desktop("linux", "v1.0.1", root=tmp_path, run=lambda *a, **k: called.append(a))
    assert called == []


def test_appimage_appdir_contains_launcher_desktop_icon_and_bundle(tmp_path):
    distribution = tmp_path / "StorageOrganizer"
    distribution.mkdir()
    executable = distribution / "StorageOrganizer"
    executable.write_text("synthetic executable", encoding="utf-8")
    appdir = tmp_path / "StorageOrganizer.AppDir"

    result = package_appimage.prepare_appdir(distribution, appdir)

    assert result == appdir
    copied_executable = appdir / "usr/bin/StorageOrganizer/StorageOrganizer"
    assert copied_executable.read_text(encoding="utf-8") == "synthetic executable"
    if os.name == "posix":
        assert os.access(appdir / "AppRun", os.X_OK)
    assert "Exec=AppRun" in (appdir / "storage-organizer.desktop").read_text(encoding="utf-8")
    assert (appdir / "storage-organizer.svg").is_file()
    assert (appdir / ".DirIcon").is_file()
    assert (appdir / "usr/share/icons/hicolor/scalable/apps/storage-organizer.svg").is_file()
    assert (appdir / "usr/share/doc/storage-organizer/THIRD-PARTY-NOTICES.md").is_file()


def test_appimage_requires_a_pyinstaller_distribution(tmp_path):
    with pytest.raises(FileNotFoundError, match="PyInstaller onedir bundle"):
        package_appimage.prepare_appdir(tmp_path / "missing", tmp_path / "AppDir")


def test_inno_setup_installs_per_user_and_does_not_request_admin():
    script = Path(__file__).resolve().parents[1] / "packaging/windows/storage-organizer.iss"
    source = script.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in source
    assert "{localappdata}\\Programs\\Storage Organizer" in source
    assert "ArchitecturesAllowed=x64" in source
    assert "recursesubdirs createallsubdirs" in source
    assert "StorageOrganizer\\*" in source


def test_build_appimage_invokes_tool_and_smoke_tests_output(tmp_path):
    distribution = tmp_path / "StorageOrganizer"
    distribution.mkdir()
    (distribution / "StorageOrganizer").write_text("synthetic executable", encoding="utf-8")
    appimagetool = tmp_path / "appimagetool"
    appimagetool.write_text("tool placeholder", encoding="utf-8")
    output = tmp_path / "release" / "StorageOrganizer-1.0.1-linux-x86_64.AppImage"
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == str(appimagetool):
            Path(command[2]).write_bytes(b"synthetic appimage")

    result = package_appimage.build_appimage(
        distribution,
        tmp_path / "AppDir",
        appimagetool,
        output,
        "1.0.1",
        run=fake_run,
        smoke_test=True,
    )

    assert result == output
    assert output.read_bytes() == b"synthetic appimage"
    assert len(calls) == 2
    assert calls[1][0] == [str(output), "--smoke-test"]
    if os.name == "posix":
        assert os.access(output, os.X_OK)


def test_build_desktop_writes_version_and_documentation(tmp_path):
    bundle = tmp_path / "StorageOrganizer"
    bundle.mkdir()

    build_desktop.add_bundle_metadata(bundle, "linux", "1.2.3")

    assert (bundle / "VERSION").read_text(encoding="utf-8").strip() == "1.2.3"
    assert (bundle / "docs/README.md").is_file()
    assert (bundle / "docs/LICENSE").is_file()
    assert (bundle / "docs/THIRD-PARTY-NOTICES.md").is_file()


def test_frozen_smoke_test_uses_offscreen_qt(tmp_path, monkeypatch):
    bundle = tmp_path / "StorageOrganizer"
    bundle.mkdir()
    executable = bundle / "StorageOrganizer"
    executable.write_text("placeholder", encoding="utf-8")
    calls = []
    monkeypatch.setattr(build_desktop.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    build_desktop.smoke_test_bundle("linux", bundle)

    assert calls[0][0][0] == [str(executable), "--smoke-test"]
    assert calls[0][1]["env"]["QT_QPA_PLATFORM"] == "offscreen"
    assert calls[0][1]["timeout"] == 90


def test_desktop_packaging_constraints_pin_compatible_build_tools():
    constraints = Path(__file__).resolve().parents[1] / "packaging/constraints-desktop.txt"
    text = constraints.read_text(encoding="utf-8")
    assert "PySide6==6.12.0" in text
    assert "PyInstaller==6.22.3" in text
    assert "Pillow==13.0.0" in text
    assert "pypdf==6.21.4" in text


def test_builder_defaults_to_project_version():
    root = Path(__file__).resolve().parents[1]
    expected = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert build_desktop.project_version() == expected


def test_macos_dmg_and_release_ci_include_required_notice_file():
    root = Path(__file__).resolve().parents[1]
    dmg_script = (root / "scripts/package_macos_dmg.sh").read_text(encoding="utf-8")
    installer = (root / "packaging/windows/storage-organizer.iss").read_text(encoding="utf-8")
    assert 'THIRD-PARTY-NOTICES.md' in dmg_script
    assert "StorageOrganizer\\*" in installer
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--version 1.0.1" not in ci
    assert "runner: macos-26" in ci


def test_appimage_rejects_overlapping_distribution_and_appdir(tmp_path):
    distribution = tmp_path / "StorageOrganizer"
    distribution.mkdir()
    (distribution / "StorageOrganizer").write_text("synthetic executable", encoding="utf-8")
    with pytest.raises(ValueError, match="must not overlap"):
        package_appimage.prepare_appdir(distribution, distribution / "AppDir")


def test_release_publication_is_blocked_until_license_review_is_approved():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish:", 1)[1]
    assert "vars.NATIVE_RELEASE_LICENSE_APPROVED == 'true'" in publish_job
