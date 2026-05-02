import os
import sys
from pathlib import Path

import static_ffmpeg


def ensure_bundled_ffmpeg_on_path() -> None:
    static_ffmpeg.add_paths(weak=True)


def _search_dirs_ffmpeg_lib() -> list[Path]:
    if sys.platform == "darwin":
        candidates = [
            Path("/opt/homebrew/opt/ffmpeg/lib"),   # Homebrew Apple Silicon
            Path("/usr/local/opt/ffmpeg/lib"),       # Homebrew Intel
            Path("/opt/local/lib"),                  # MacPorts
            Path("/usr/local/lib"),                  # source build
        ]
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        if conda_prefix:
            candidates.append(Path(conda_prefix) / "lib")
        return candidates
    if sys.platform.startswith("linux"):
        candidates = [
            Path("/usr/lib/x86_64-linux-gnu"),      # Debian/Ubuntu x86_64
            Path("/usr/lib/aarch64-linux-gnu"),      # Debian/Ubuntu ARM64
            Path("/usr/lib64"),                      # RHEL/Fedora/SUSE
            Path("/usr/lib"),                        # generic
            Path("/usr/local/lib"),                  # source build / Arch
        ]
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        if conda_prefix:
            candidates.append(Path(conda_prefix) / "lib")
        return candidates
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
        print(
            "경고: Windows에서는 FFmpeg 공유 라이브러리 경로 자동 설정이 지원되지 않습니다. "
            "torchaudio/torchcodec 오류 발생 시 FFmpeg DLL을 PATH에 직접 추가하세요."
        )
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
