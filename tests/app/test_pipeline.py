def test_run_pipeline_calls_download_then_separation(monkeypatch, tmp_path):
    """URL이 주어지면 download가 먼저 실행되고 그 결과 Path가 separation의 input_file로 전달되어야 한다."""
    calls: list = []
    fake_downloaded = tmp_path / "song.mp3"
    fake_downloaded.touch()

    def fake_download(url, output_path):
        calls.append(("download", url, output_path))
        return fake_downloaded

    def fake_separate(input_file, output_dir, stems, use_gpu):
        calls.append(("separate", input_file, output_dir, stems, use_gpu))
        return True

    monkeypatch.setattr("src.app.main.download_audio", fake_download)
    monkeypatch.setattr("src.app.main.separate_audio", fake_separate)

    from src.app.main import run_pipeline

    ok = run_pipeline(
        url="https://youtu.be/abc",
        stem=None,
        use_gpu=False,
        base_dir=tmp_path,
    )

    assert ok is True
    assert len(calls) == 2
    assert calls[0][0] == "download"
    assert calls[0][1] == "https://youtu.be/abc"
    assert calls[1][0] == "separate"
    assert calls[1][1] == fake_downloaded
    assert calls[1][4] is False


def test_run_pipeline_returns_false_when_download_fails(monkeypatch, tmp_path):
    """download가 None을 반환하면 separation은 호출되지 않고 False를 반환한다."""
    calls: list = []

    def fake_download(url, output_path):
        calls.append("download")
        return None

    def fake_separate(input_file, output_dir, stems, use_gpu):
        calls.append("separate")
        return True

    monkeypatch.setattr("src.app.main.download_audio", fake_download)
    monkeypatch.setattr("src.app.main.separate_audio", fake_separate)

    from src.app.main import run_pipeline

    ok = run_pipeline(
        url="https://youtu.be/bad",
        stem=None,
        use_gpu=False,
        base_dir=tmp_path,
    )

    assert ok is False
    assert calls == ["download"]


def test_main_prints_korean_error_and_exits_when_pipeline_fails(monkeypatch, capsys):
    """run_pipeline이 False를 반환하면 main은 한국어 실패 메시지를 stderr로 출력하고 exit 1."""
    import sys as _sys

    import pytest

    monkeypatch.setattr(
        _sys,
        "argv",
        ["main.py", "--url", "https://youtu.be/x"],
    )
    monkeypatch.setattr(
        "src.app.main.check_hardware_compatibility",
        lambda: {
            "can_run": True,
            "warning": "",
            "cuda_available": False,
            "ram_gb": 16.0,
        },
    )
    monkeypatch.setattr("src.app.main.run_pipeline", lambda **kwargs: False)

    from src.app.main import main

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "처리 실패" in captured.err
