from unittest.mock import MagicMock


def test_download_audio_uses_prepare_filename_for_sanitized_title(monkeypatch, tmp_path):
    """yt-dlp가 title을 sanitize하면(예: '/', '?' → '_'), download_audio는
    prepare_filename 기반의 실제 저장 경로(.mp3)로 반환해야 한다."""
    raw_title = "Song / Title? 2025"
    sanitized_stem = "Song _ Title_ 2025"

    sanitized_mp3 = tmp_path / f"{sanitized_stem}.mp3"
    sanitized_mp3.touch()

    fake_ydl = MagicMock()
    fake_ydl.__enter__.return_value = fake_ydl
    fake_ydl.__exit__.return_value = False
    fake_ydl.extract_info.return_value = {"title": raw_title}
    fake_ydl.prepare_filename.return_value = str(tmp_path / f"{sanitized_stem}.webm")

    monkeypatch.setattr("src.features.download.yt_dlp.YoutubeDL", lambda opts: fake_ydl)

    from src.features.download import download_audio

    result = download_audio("https://youtu.be/abc", tmp_path)

    assert result == sanitized_mp3
    fake_ydl.prepare_filename.assert_called_once()


def test_download_audio_returns_none_when_file_missing(monkeypatch, tmp_path):
    """prepare_filename이 가리키는 경로에 실제 파일이 없으면 None을 반환."""
    fake_ydl = MagicMock()
    fake_ydl.__enter__.return_value = fake_ydl
    fake_ydl.__exit__.return_value = False
    fake_ydl.extract_info.return_value = {"title": "nothing"}
    fake_ydl.prepare_filename.return_value = str(tmp_path / "nothing.webm")

    monkeypatch.setattr("src.features.download.yt_dlp.YoutubeDL", lambda opts: fake_ydl)

    from src.features.download import download_audio

    result = download_audio("https://youtu.be/missing", tmp_path)

    assert result is None


def test_download_audio_warns_in_korean_when_extract_info_returns_none(
    monkeypatch, tmp_path, capsys
):
    """extract_info가 None을 반환하면(예: private/삭제된 영상) 한국어 경고 후 None 반환.
    prepare_filename은 호출되어서는 안 된다."""
    fake_ydl = MagicMock()
    fake_ydl.__enter__.return_value = fake_ydl
    fake_ydl.__exit__.return_value = False
    fake_ydl.extract_info.return_value = None

    monkeypatch.setattr("src.features.download.yt_dlp.YoutubeDL", lambda opts: fake_ydl)

    from src.features.download import download_audio

    result = download_audio("https://youtu.be/private", tmp_path)

    assert result is None
    fake_ydl.prepare_filename.assert_not_called()
    captured = capsys.readouterr()
    assert "영상 정보를 가져올 수 없습니다" in captured.out
