#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 VERSION" >&2
  exit 2
fi

VERSION="$1"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/dist/StorageOrganizer.app"
STAGING="$ROOT/build/dmg-root"
OUTPUT="$ROOT/release-assets/StorageOrganizer-${VERSION}-macos-$(uname -m).dmg"

if [[ ! -d "$APP" ]]; then
  echo "PyInstaller application bundle not found: $APP" >&2
  exit 1
fi

rm -rf "$STAGING"
mkdir -p "$STAGING" "$ROOT/release-assets"
cp -R "$APP" "$STAGING/StorageOrganizer.app"
ln -s /Applications "$STAGING/Applications"
cp "$ROOT/README.md" "$STAGING/README.md"
cp "$ROOT/LICENSE" "$STAGING/LICENSE"
cp "$ROOT/THIRD-PARTY-NOTICES.md" "$STAGING/THIRD-PARTY-NOTICES.md"

hdiutil create \
  -volname "Storage Organizer" \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$OUTPUT"

hdiutil verify "$OUTPUT"
MOUNT_POINT="$ROOT/build/dmg-verify"
mkdir -p "$MOUNT_POINT"
cleanup_mount() {
  hdiutil detach "$MOUNT_POINT" >/dev/null 2>&1 || true
  rmdir "$MOUNT_POINT" >/dev/null 2>&1 || true
}
trap cleanup_mount EXIT
hdiutil attach -readonly -nobrowse -mountpoint "$MOUNT_POINT" "$OUTPUT"
test -d "$MOUNT_POINT/StorageOrganizer.app"
cleanup_mount
trap - EXIT
echo "Built and verified macOS disk image: $OUTPUT"
