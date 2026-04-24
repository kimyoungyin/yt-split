import os
import sys
from pathlib import Path


def test_ensure_bundled_ffmpeg_calls_static_ffmpeg_add_paths_weak(monkeypatch) -> None:
    """번들 ffmpeg PATH 보강 시 static_ffmpeg.add_paths(weak=True)를 호출해야 한다."""
    calls: list[dict[str, object]] = []

    def spy(weak: bool = False, download_dir: object = None) -> bool:
        calls.append({"weak": weak, "download_dir": download_dir})
        return True

    monkeypatch.setattr("static_ffmpeg.add_paths", spy)

    from src.features.ffmpeg_env import ensure_bundled_ffmpeg_on_path

    ensure_bundled_ffmpeg_on_path()

    assert len(calls) == 1
    assert calls[0]["weak"] is True


def test_system_has_ffmpeg_shared_libs_true_when_libavutil_in_search_dir(
    monkeypatch, tmp_path: Path
) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libavutil.60.dylib").touch()
    monkeypatch.setattr(
        "src.features.ffmpeg_env._search_dirs_ffmpeg_lib",
        lambda: [lib_dir],
    )

    from src.features.ffmpeg_env import system_has_ffmpeg_shared_libs_for_torchcodec

    assert system_has_ffmpeg_shared_libs_for_torchcodec() is True


def test_system_has_ffmpeg_shared_libs_false_when_dirs_lack_libavutil(
    monkeypatch, tmp_path: Path
) -> None:
    empty_dir = tmp_path / "empty_lib"
    empty_dir.mkdir()
    monkeypatch.setattr(
        "src.features.ffmpeg_env._search_dirs_ffmpeg_lib",
        lambda: [empty_dir],
    )

    from src.features.ffmpeg_env import system_has_ffmpeg_shared_libs_for_torchcodec

    assert system_has_ffmpeg_shared_libs_for_torchcodec() is False


def test_ensure_shared_ffmpeg_prepends_brew_ffmpeg_lib_to_dyld_on_darwin(
    monkeypatch, tmp_path: Path
) -> None:
    """macOS에서 libavutil가 있는 ffmpeg lib 경로를 찾으면 DYLD_LIBRARY_PATH 앞에 붙인다."""
    lib_dir = tmp_path / "opt" / "ffmpeg" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "libavutil.60.dylib").touch()

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        "src.features.ffmpeg_env._search_dirs_ffmpeg_lib",
        lambda: [lib_dir],
    )
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/foo")

    from src.features.ffmpeg_env import ensure_shared_ffmpeg_for_torchcodec

    ensure_shared_ffmpeg_for_torchcodec()

    dyp = os.environ["DYLD_LIBRARY_PATH"]
    parts = [p for p in dyp.split(os.pathsep) if p]
    assert str(lib_dir) == parts[0]
    assert "/foo" in parts[1:]
