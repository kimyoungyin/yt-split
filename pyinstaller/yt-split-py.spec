# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the yt-split sidecar binary.

Builds a one-folder distribution with PyTorch + Demucs + yt-dlp bundled.
Run via `pyinstaller/build.sh`, which renames `dist/yt-split-py` to
`dist/yt-split-py-<target-triple>` and stages it under `src-tauri/binaries/`.
"""
import os
import sys

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# Demucs ships pretrained model metadata under demucs/remote/. Without these
# the runtime call to demucs.pretrained.get_model_from_args fails to find
# htdemucs.yaml.
demucs_datas = collect_data_files("demucs", includes=["remote/*"])

# torchcodec ships per-FFmpeg-version `.dylib` / `.so` files plus encoder
# Python modules; both must be staged or torchaudio.save dies at runtime
# trying to dlopen libtorchcodec_coreN.
torchcodec_datas = collect_data_files("torchcodec")

# yt-dlp ships a large set of extractor modules; collecting submodules avoids
# ModuleNotFoundError for the many lazy imports.
# numpy 2.x re-exports numpy._core under numpy.core via a lazy compatibility
# shim; PyInstaller's static analysis misses those .py files unless we ask
# for every numpy submodule explicitly.
hidden = []
hidden += collect_submodules("demucs")
hidden += collect_submodules("yt_dlp")
hidden += collect_submodules("torchaudio")
hidden += collect_submodules("torchcodec")
hidden += collect_submodules("numpy")

# Collect torchcodec's bundled .dylib / .so files (libtorchcodec_core*).
binaries = []
binaries += collect_dynamic_libs("torchcodec")

# Stage the system FFmpeg shared libraries that torchcodec links against
# (libavutil, libavcodec, libavformat, ...). torchcodec dylibs reference them
# by @rpath so PyInstaller's bootloader resolves them from _MEIPASS at runtime.
def _ffmpeg_lib_dir() -> str | None:
    if sys.platform == "darwin":
        for candidate in ("/opt/homebrew/opt/ffmpeg/lib", "/usr/local/opt/ffmpeg/lib"):
            if os.path.isdir(candidate):
                return candidate
    if sys.platform == "win32":
        # Windows "full-shared" FFmpeg build: DLLs live under bin/.
        # Install via: choco install ffmpeg  or  scoop install ffmpeg
        candidates = [
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "ffmpeg", "bin"),
        ]
        for c in candidates:
            if os.path.isdir(c) and any(
                f.startswith("avutil") and f.endswith(".dll") for f in os.listdir(c)
            ):
                return c
    if sys.platform.startswith("linux"):
        for candidate in (
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib/aarch64-linux-gnu",
            "/usr/lib64",
            "/usr/lib",
        ):
            if os.path.isdir(candidate) and any(
                f.startswith("libavutil") for f in os.listdir(candidate)
            ):
                return candidate
        # ldconfig -p fallback for non-standard distro layouts (OD-3)
        try:
            import subprocess
            out = subprocess.check_output(
                ["ldconfig", "-p"], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "libavutil" in line and "=>" in line:
                    lib_path = line.split("=>")[-1].strip()
                    return os.path.dirname(lib_path)
        except Exception:
            pass
    return None


_ffmpeg_dir = _ffmpeg_lib_dir()
if _ffmpeg_dir:
    if sys.platform == "win32":
        # Windows DLL names: avutil-59.dll, avcodec-61.dll, etc. (no "lib" prefix)
        for fname in os.listdir(_ffmpeg_dir):
            if fname.endswith(".dll") and (
                fname.startswith("av")
                or fname.startswith("sw")
                or fname.startswith("postproc")
            ):
                full = os.path.join(_ffmpeg_dir, fname)
                if os.path.exists(full):
                    binaries.append((full, "."))
    else:
        suffix = ".dylib" if sys.platform == "darwin" else ".so"
        for fname in os.listdir(_ffmpeg_dir):
            if fname.endswith(suffix) and (
                fname.startswith("libav")
                or fname.startswith("libsw")
                or fname.startswith("libpost")
            ):
                full = os.path.join(_ffmpeg_dir, fname)
                if os.path.exists(full):
                    binaries.append((full, "."))

a = Analysis(
    ["../src/app/main.py"],
    pathex=[".."],
    binaries=binaries,
    datas=demucs_datas + torchcodec_datas,
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
