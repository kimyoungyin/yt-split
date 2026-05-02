import yt_dlp
from pathlib import Path
from typing import Any, Dict, Optional

from src.features.progress import ProgressEmitter


def _make_progress_hook(emitter: ProgressEmitter):
    """yt-dlp progress hook that forwards the download ratio to the emitter."""

    def hook(d: Dict[str, Any]) -> None:
        if not emitter.enabled:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes")
            if total and downloaded is not None and total > 0:
                emitter.emit("progress", stage="download", value=min(downloaded / total, 1.0))
        elif status == "finished":
            emitter.emit("progress", stage="download", value=1.0)

    return hook


def download_audio(
    url: str,
    output_path: Path,
    emitter: Optional[ProgressEmitter] = None,
) -> Optional[Path]:
    """
    Extracts audio from a YouTube URL using yt-dlp.
    """
    ydl_opts: Dict[str, Any] = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': str(output_path / '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
    }
    if emitter is not None and emitter.enabled:
        ydl_opts['progress_hooks'] = [_make_progress_hook(emitter)]
        ydl_opts['quiet'] = True
        ydl_opts['no_warnings'] = True

    if emitter is not None and emitter.enabled:
        emitter.emit("stage", stage="download", status="start", url=url)
    else:
        print(f"오디오 다운로드 중: {url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                msg = "영상 정보를 가져올 수 없습니다."
                if emitter is not None and emitter.enabled:
                    emitter.emit("error", stage="download", message=msg)
                else:
                    print(msg)
                return None
            source_path = Path(ydl.prepare_filename(info))
            downloaded_file = source_path.with_suffix(".mp3")

            if downloaded_file.exists():
                if emitter is not None and emitter.enabled:
                    emitter.emit("stage", stage="download", status="done", path=str(downloaded_file.resolve()))
                else:
                    print(f"다운로드 완료: {downloaded_file}")
                return downloaded_file
            return None

    except Exception as e:
        msg = f"다운로드 오류: {str(e)}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="download", message=msg)
        else:
            print(msg)
        return None
