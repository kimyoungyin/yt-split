import os
import sys
from pathlib import Path

import static_ffmpeg


def ensure_bundled_ffmpeg_on_path() -> None:
    static_ffmpeg.add_paths(weak=True)


def _search_dirs_ffmpeg_lib() -> list[Path]:
    if sys.platform == "darwin":
        return [
            Path("/opt/homebrew/opt/ffmpeg/lib"),
            Path("/usr/local/opt/ffmpeg/lib"),
        ]
    if sys.platform.startswith("linux"):
        return [
            Path("/usr/lib/x86_64-linux-gnu"),
            Path("/usr/lib/aarch64-linux-gnu"),
            Path("/usr/lib64"),
        ]
    return []


def _dir_has_ffmpeg_shared_libraries(lib_dir: Path) -> bool:
    if not lib_dir.is_dir():
        return False
    for child in lib_dir.iterdir():
        if child.name.startswith("libavutil") and not child.is_dir():
            return True
    return False


def system_has_ffmpeg_shared_libs_for_torchcodec() -> bool:
    """True if a known search path already contains FFmpeg shared libs (e.g. libavutil), for tests and skipif."""
    return any(
        _dir_has_ffmpeg_shared_libraries(d) for d in _search_dirs_ffmpeg_lib()
    )


def ensure_shared_ffmpeg_for_torchcodec() -> None:
    """Put FFmpeg shared library dir on the linker path for torchcodec (Demucs -> torchaudio.save)."""
    if sys.platform == "win32":
        return

    key = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    for lib_dir in _search_dirs_ffmpeg_lib():
        if not _dir_has_ffmpeg_shared_libraries(lib_dir):
            continue
        prefix = str(lib_dir)
        existing = os.environ.get(key, "")
        if not existing:
            os.environ[key] = prefix
            return
        parts = [p for p in existing.split(os.pathsep) if p]
        if prefix in parts:
            return
        os.environ[key] = f"{prefix}{os.pathsep}{existing}"
        return
