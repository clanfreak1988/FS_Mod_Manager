# Builds FSModManager.exe (Windows onefile build) via PyInstaller.
#
# Must be run ON Windows - PyInstaller does not cross-compile.
# Run from anywhere; paths are resolved relative to the repo root.
#
# Requirements:
#   - active venv with the project + pyinstaller installed
#     (pip install -e . ; pip install pyinstaller)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

Set-Location $RepoRoot

Write-Host "==> Building onefile exe with PyInstaller"
pyinstaller --noconfirm --clean packaging\windows\fsmodmanager.spec

Write-Host "==> Done: $RepoRoot\dist\FSModManager.exe"
