# Build the yt-split-py sidecar with PyInstaller and stage it under
# src-tauri\binaries\<target-triple>\ for Tauri's bundle.resources lookup.
#
# Prerequisites:
#   - Python 3.10+ with requirements.txt installed
#   - FFmpeg "full-shared" build on PATH or under C:\ffmpeg\bin (for spec DLL collection)
#   - Run from repo root or the pyinstaller\ directory
#
# Usage:
#   .\pyinstaller\build.ps1
$ErrorActionPreference = "Stop"

$TRIPLE = "x86_64-pc-windows-msvc"

# Resolve repo root regardless of where the script is invoked from.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path "$ScriptDir\..").Path

Set-Location $ROOT

$DIST_NAME = "yt-split-py-$TRIPLE"
$TAURI_BIN_DIR = Join-Path $ROOT "src-tauri\binaries"

Write-Host "[build] target = $TRIPLE"

# Clean previous build artifacts.
foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}

pyinstaller pyinstaller\yt-split-py.spec --noconfirm --distpath dist --workpath build

# Rename to target-triple folder.
$srcDir = Join-Path $ROOT "dist\yt-split-py"
$dstDist = Join-Path $ROOT "dist\$DIST_NAME"
if (Test-Path $dstDist) { Remove-Item -Recurse -Force $dstDist }
Rename-Item -Path $srcDir -NewName $DIST_NAME

# Stage under src-tauri\binaries\.
if (-not (Test-Path $TAURI_BIN_DIR)) { New-Item -ItemType Directory -Path $TAURI_BIN_DIR | Out-Null }
$stageTarget = Join-Path $TAURI_BIN_DIR $DIST_NAME
if (Test-Path $stageTarget) { Remove-Item -Recurse -Force $stageTarget }
Copy-Item -Recurse -Path $dstDist -Destination $stageTarget

Write-Host "[build] staged: $stageTarget\yt-split-py.exe"

# Patch tauri.conf.json bundle.resources to the current platform triple so
# `pnpm build:app` includes exactly this sidecar folder and nothing else.
# Tauri v2 fails the build if a listed resource path does not exist on disk.
$CONF = Join-Path $ROOT "src-tauri\tauri.conf.json"
$conf = Get-Content $CONF -Raw | ConvertFrom-Json
$conf.bundle.resources = @("binaries/yt-split-py-$TRIPLE")
# Use the 2-arg overload — .NET Core (pwsh 7) WriteAllText defaults to UTF-8 no-BOM.
# The 3-arg form with New-Object UTF8Encoding fails overload resolution on pwsh 7.
$jsonContent = $conf | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($CONF, $jsonContent + "`n")

Write-Host "[build] patched tauri.conf.json bundle.resources → binaries/yt-split-py-$TRIPLE"
