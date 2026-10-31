# Desktop packaging and release artifacts

Storage Organizer keeps its Python wheel and source distribution and additionally builds native desktop packages from tagged source. All native packages launch the same PySide6 GUI and retain the application's copy-only and SHA-256 verification behavior.

## Release targets

| Asset | Build runner | Artifact | Notes |
|---|---|---|---|
| Windows | Windows x64 | `StorageOrganizer-Setup-VERSION-windows-x64.exe` | Per-user Inno Setup installer; no administrator rights required for the default install location |
| macOS Apple Silicon | macOS arm64 | `StorageOrganizer-VERSION-macos-arm64.dmg` | Drag `StorageOrganizer.app` to Applications |
| macOS Intel | macOS x86_64 | `StorageOrganizer-VERSION-macos-x86_64.dmg` | Separate native build; not a universal binary |
| Linux | Ubuntu 22.04 x86_64 | `StorageOrganizer-VERSION-linux-x86_64.AppImage` | AppImage bundles the PyInstaller application directory; system graphics and desktop integration libraries may still be required |
| Python | Ubuntu | wheel and source archive | Cross-platform Python installation, including CLI entry point |

The Linux AppImage is built on Ubuntu 22.04 to avoid raising its glibc baseline unnecessarily. It targets x86_64 and glibc 2.35 or newer. The macOS packages target macOS 14 or newer. ARM Linux packaging is not part of this phase.

Desktop build dependencies are constrained in `packaging/constraints-desktop.txt` (PySide6 6.12.0, PyInstaller 6.22.3, Pillow 13.0.0, and pypdf 6.21.4) so new upstream releases cannot silently change the tested build set. The frozen bundles explicitly collect PySide6, shiboken6, Pillow, and pypdf. `ffprobe` remains an optional system dependency and is not included in the installers. The bundle includes `THIRD-PARTY-NOTICES.md`; maintainers must still complete the exact Qt component/license/source/relinking audit described there before publishing native packages.

## Build locally

Install the application and packaging extra in a Python 3.11+ virtual environment:

```bash
python -m pip install -e ".[gui,media,packaging]" -c packaging/constraints-desktop.txt
python scripts/build_desktop.py --target linux --smoke-test
```

Run the builder on the matching native OS. Supported `--target` values are `windows`, `macos`, and `linux`; cross-building between operating systems is intentionally rejected. The builder writes a PyInstaller onedir bundle under `dist/` and executes its frozen GUI in Qt's offscreen mode to verify imports and full MainWindow construction.

For Linux, install `libfuse2` and run the AppImage packager with AppImageKit's `appimagetool` 1.9.1:

```bash
python scripts/package_appimage.py \
  --version 1.0.1 \
  --appimagetool ./appimagetool-x86_64.AppImage
```

For Windows, compile `packaging/windows/storage-organizer.iss` with Inno Setup using `/DAppVersion=VERSION`. For macOS, run `scripts/package_macos_dmg.sh VERSION` after the native PyInstaller build. The release workflow performs these steps on native GitHub-hosted runners and uploads the resulting packages to the GitHub Release.

## Third-party licensing

Native builds redistribute PySide6/Qt runtime libraries. Qt Community components have a mix of LGPL and GPL licensing, and the terms vary by module. The `onedir` application layout keeps library binaries separate, but this alone does not establish LGPL compliance. Review the exact platform bundle, provide required licenses and matching source/materials, and confirm users can exercise any required replace/relink rights before publication. See [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

## Signing and trust

Native publication is explicitly gated: set the repository Actions variable `NATIVE_RELEASE_LICENSE_APPROVED=true` only after the exact Qt/PySide6 component inventory, applicable license texts, corresponding source materials, and replace/relink rights have been reviewed and satisfied. Without this variable, CI may build/test candidate artifacts but the release publish job is skipped.

The initial native artifacts are not code-signed or notarized. Windows SmartScreen and macOS Gatekeeper may display publisher/developer warnings. On macOS, users may need to Control-click the app and choose **Open** for the first launch. A Developer ID certificate, Apple notarization credentials, and a Windows code-signing certificate are not stored in this repository; signing should be enabled only after those secrets and the corresponding release policy are configured.

## Integrity

Each GitHub Release includes `SHA256SUMS.txt` covering the wheel, source archive, Windows installer, both macOS disk images, and Linux AppImage. Verify the selected downloaded asset before installing it by comparing `sha256sum <downloaded-file>` with that filename’s line in `SHA256SUMS.txt`. If you have downloaded every asset listed in the checksum file, you can verify all of them at once:

```bash
sha256sum --check SHA256SUMS.txt
```

On Windows PowerShell, compare the output of `Get-FileHash -Algorithm SHA256 .\\StorageOrganizer-Setup-VERSION-windows-x64.exe` with the corresponding entry in `SHA256SUMS.txt`.
