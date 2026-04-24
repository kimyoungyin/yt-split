def test_ensure_bundled_ffmpeg_calls_static_ffmpeg_add_paths_weak(monkeypatch):
    """번들 ffmpeg PATH 보강 시 static_ffmpeg.add_paths(weak=True)를 호출해야 한다."""
    calls: list = []

    def spy(weak: bool = False, download_dir=None) -> bool:
        calls.append({"weak": weak, "download_dir": download_dir})
        return True

    monkeypatch.setattr("static_ffmpeg.add_paths", spy)

    from src.features.ffmpeg_env import ensure_bundled_ffmpeg_on_path

    ensure_bundled_ffmpeg_on_path()

    assert len(calls) == 1
    assert calls[0]["weak"] is True
