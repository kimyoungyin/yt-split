import yt_dlp
from pathlib import Path
from typing import Optional


def download_audio(url: str, output_path: Path) -> Optional[Path]:
    """
    Extracts audio from a YouTube URL using yt-dlp.
    """
    ydl_opts = {
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

    try:
        print(f"오디오 다운로드 중: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                print("영상 정보를 가져올 수 없습니다.")
                return None
            source_path = Path(ydl.prepare_filename(info))
            downloaded_file = source_path.with_suffix(".mp3")

            if downloaded_file.exists():
                print(f"다운로드 완료: {downloaded_file}")
                return downloaded_file
            return None

    except Exception as e:
        print(f"다운로드 오류: {str(e)}")
        return None