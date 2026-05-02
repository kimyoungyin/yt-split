#!/usr/bin/env bash
# Build the yt-split-py sidecar with PyInstaller and stage it under
# src-tauri/binaries/<target-triple>/ for Tauri's externalBin lookup.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)   TRIPLE="aarch64-apple-darwin" ;;
  Darwin-x86_64)  TRIPLE="x86_64-apple-darwin" ;;
  Linux-x86_64)   TRIPLE="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64)  TRIPLE="aarch64-unknown-linux-gnu" ;;
  *)
    echo "Unsupported platform: $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac

DIST_NAME="yt-split-py-${TRIPLE}"
TAURI_BIN_DIR="${ROOT}/src-tauri/binaries"

echo "[build] target = ${TRIPLE}"
rm -rf build dist

pyinstaller pyinstaller/yt-split-py.spec --noconfirm --distpath dist --workpath build

# PyInstaller writes to dist/yt-split-py/. Rename to a target-triple folder
# so we can ship multiple architectures alongside each other later.
rm -rf "dist/${DIST_NAME}"
mv "dist/yt-split-py" "dist/${DIST_NAME}"

mkdir -p "${TAURI_BIN_DIR}"
rm -rf "${TAURI_BIN_DIR}/${DIST_NAME}"
cp -R "dist/${DIST_NAME}" "${TAURI_BIN_DIR}/"

echo "[build] staged: ${TAURI_BIN_DIR}/${DIST_NAME}/yt-split-py"
