import static_ffmpeg


def ensure_bundled_ffmpeg_on_path() -> None:
    static_ffmpeg.add_paths(weak=True)
