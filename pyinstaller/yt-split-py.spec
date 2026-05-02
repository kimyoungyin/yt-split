# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the yt-split sidecar binary.

Builds a one-folder distribution with PyTorch + Demucs + yt-dlp bundled.
Run via `pyinstaller/build.sh`, which renames `dist/yt-split-py` to
`dist/yt-split-py-<target-triple>` and stages it under `src-tauri/binaries/`.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Demucs ships pretrained model metadata under demucs/remote/. Without these
# the runtime call to demucs.pretrained.get_model_from_args fails to find
# htdemucs.yaml.
demucs_datas = collect_data_files("demucs", includes=["remote/*"])

# yt-dlp ships a large set of extractor modules; collecting submodules avoids
# ModuleNotFoundError for the many lazy imports.
hidden = []
hidden += collect_submodules("demucs")
hidden += collect_submodules("yt_dlp")
hidden += collect_submodules("torchaudio")

a = Analysis(
    ["../src/app/main.py"],
    pathex=[".."],
    binaries=[],
    datas=demucs_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim large unused tooling that PyInstaller would otherwise pull in.
        "tkinter",
        "matplotlib",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yt-split-py",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="yt-split-py",
)
