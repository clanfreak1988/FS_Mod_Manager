#!/usr/bin/env bash
# Builds a self-contained Linux AppImage for FS Mod Manager.
#
# Pipeline: PyInstaller onefile binary -> AppDir -> appimagetool.
# Run from anywhere; paths are resolved relative to the repo root.
#
# Requirements:
#   - active venv with the project + pyinstaller installed
#     (pip install -e . && pip install pyinstaller)
#   - appimagetool on PATH, or set APPIMAGETOOL=/path/to/appimagetool
#   - FUSE available (or appimagetool falls back to --appimage-extract-and-run)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"

cd "$REPO_ROOT"

echo "==> Building onefile binary with PyInstaller"
pyinstaller --noconfirm --clean packaging/linux/fsmodmanager.spec

APPDIR="$REPO_ROOT/build/FSModManager.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

echo "==> Assembling AppDir"
cp "$REPO_ROOT/dist/fsmodmanager" "$APPDIR/usr/bin/fsmodmanager"
cp "$REPO_ROOT/packaging/linux/fsmodmanager.desktop" "$APPDIR/fsmodmanager.desktop"
cp "$REPO_ROOT/src/fsmodmanager/resources/icon.png" "$APPDIR/fsmodmanager.png"
ln -sf usr/bin/fsmodmanager "$APPDIR/AppRun"

echo "==> Running appimagetool"
if ! command -v "$APPIMAGETOOL" >/dev/null 2>&1 && [ ! -x "$APPIMAGETOOL" ]; then
    echo "error: appimagetool not found. Set APPIMAGETOOL=/path/to/appimagetool" >&2
    exit 1
fi
OUTPUT="$REPO_ROOT/dist/FSModManager-x86_64.AppImage"
mkdir -p "$REPO_ROOT/dist"
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

echo "==> Done: $OUTPUT"
