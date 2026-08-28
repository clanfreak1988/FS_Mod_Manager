# PyInstaller spec for the Linux onefile build.
#
# Build with:
#   pyinstaller packaging/linux/fsmodmanager.spec
#
# Run from the repo root so relative paths below resolve correctly.

from pathlib import Path

block_cipher = None

repo_root = Path.cwd()
resources_dir = repo_root / "src" / "fsmodmanager" / "resources"

a = Analysis(
    [str(repo_root / "main.py")],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=[
        (str(resources_dir / "icon.png"), "fsmodmanager/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fsmodmanager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(resources_dir / "icon.png"),
)
