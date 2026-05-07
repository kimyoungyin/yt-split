import json


def test_run_pipeline_calls_download_then_separation(monkeypatch, tmp_path):
    """URL이 주어지면 download가 먼저 실행되고 그 결과 Path가 separation의 input_file로 전달되어야 한다."""
    calls: list = []
    fake_downloaded = tmp_path / "song.mp3"
    fake_downloaded.touch()

    def fake_download(url, output_path, emitter=None):
        calls.append(("download", url, output_path))
        return fake_downloaded, "Test Song"

    def fake_separate(input_file, project_dir, stems, device, emitter=None):
        calls.append(("separate", input_file, project_dir, stems, device))
        return {"vocals": project_dir / "stems" / "vocals.wav"}

    def fake_create_meta(**kwargs):
        calls.append(("meta", kwargs["project_id"], kwargs["title"]))
        return tmp_path / "projects" / f"{kwargs['project_id']}.json"

    monkeypatch.setattr("src.app.main.download_audio", fake_download)
    monkeypatch.setattr("src.app.main.separate_audio", fake_separate)
    monkeypatch.setattr("src.app.main.create_project_metadata", fake_create_meta)

    from src.app.main import run_pipeline

    ok = run_pipeline(
        url="https://youtu.be/abc",
        stem=None,
        device="cpu",
        base_dir=tmp_path,
    )

    assert ok is True
    assert calls[0][0] == "download"
    assert calls[0][1] == "https://youtu.be/abc"
    assert calls[1][0] == "separate"
    assert calls[1][1] == fake_downloaded
    assert calls[1][4] == "cpu"
    assert calls[2][0] == "meta"
    assert calls[2][2] == "Test Song"


def test_run_pipeline_returns_false_when_download_fails(monkeypatch, tmp_path):
    """download가 (None, '') 을 반환하면 separation은 호출되지 않고 False를 반환한다."""
    calls: list = []

    def fake_download(url, output_path, emitter=None):
        calls.append("download")
        return None, ""

    def fake_separate(input_file, project_dir, stems, device, emitter=None):
        calls.append("separate")
        return {"vocals": project_dir / "stems" / "vocals.wav"}

    monkeypatch.setattr("src.app.main.download_audio", fake_download)
    monkeypatch.setattr("src.app.main.separate_audio", fake_separate)

    from src.app.main import run_pipeline

    ok = run_pipeline(
        url="https://youtu.be/bad",
        stem=None,
        device="cpu",
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
        lambda check_path=None: {
            "can_run": True,
            "warning": "",
            "cuda_available": False,
            "mps_available": False,
            "demucs_device": "cpu",
            "ram_gb": 16.0,
            "vram_gb": 0.0,
            "free_space_gb": 100.0,
        },
    )
    monkeypatch.setattr("src.app.main.ensure_bundled_ffmpeg_on_path", lambda: None)
    monkeypatch.setattr("src.app.main.ensure_shared_ffmpeg_for_torchcodec", lambda: None)
    monkeypatch.setattr("src.app.main.run_pipeline", lambda **kwargs: False)

    from src.app.main import main

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "처리 실패" in captured.err


def test_main_sidecar_emits_hardware_event_on_check(monkeypatch):
    """--sidecar --check should emit exactly one NDJSON 'hardware' event on stdout.

    The sidecar emitter writes to sys.__stdout__ so demucs/yt-dlp redirect
    blocks can't divert it; we monkeypatch __stdout__ to capture the bytes.
    """
    import io
    import sys as _sys

    buf = io.StringIO()
    monkeypatch.setattr(_sys, "__stdout__", buf)
    monkeypatch.setattr(
        _sys,
        "argv",
        ["main.py", "--check", "--sidecar"],
    )
    monkeypatch.setattr(
        "src.app.main.check_hardware_compatibility",
        lambda check_path=None: {
            "can_run": True,
            "warning": "",
            "cuda_available": True,
            "mps_available": False,
            "demucs_device": "cuda",
            "ram_gb": 32.0,
            "vram_gb": 8.0,
            "free_space_gb": 200.0,
        },
    )

    from src.app.main import main

    main()

    out = buf.getvalue().strip().splitlines()
    assert len(out) == 1
    payload = json.loads(out[0])
    assert payload["type"] == "hardware"
    assert payload["demucs_device"] == "cuda"
    assert payload["ram_gb"] == 32.0


def test_main_uses_workdir_arg_for_base_dir(monkeypatch, tmp_path):
    """--workdir <path> 가 주어지면 run_pipeline.base_dir과
    check_hardware_compatibility.check_path가 모두 그 경로여야 한다."""
    import sys as _sys

    captured = {}

    def fake_check(check_path=None):
        captured["check_path"] = check_path
        return {
            "can_run": True, "warning": "",
            "cuda_available": False, "mps_available": False,
            "demucs_device": "cpu",
            "ram_gb": 16.0, "vram_gb": 0.0, "free_space_gb": 100.0,
        }

    def fake_run(**kwargs):
        captured["base_dir"] = kwargs["base_dir"]
        return True

    monkeypatch.setattr(_sys, "argv", [
        "main.py", "--url", "https://youtu.be/x",
        "--sidecar", "--workdir", str(tmp_path),
    ])
    monkeypatch.setattr("src.app.main.check_hardware_compatibility", fake_check)
    monkeypatch.setattr("src.app.main.ensure_bundled_ffmpeg_on_path", lambda: None)
    monkeypatch.setattr("src.app.main.ensure_shared_ffmpeg_for_torchcodec", lambda: None)
    monkeypatch.setattr("src.app.main.run_pipeline", fake_run)

    from src.app.main import main
    main()

    assert captured["check_path"] == tmp_path
    assert captured["base_dir"] == tmp_path


def test_main_workdir_defaults_to_cwd_when_not_specified(monkeypatch):
    """--workdir 미지정 시 base_dir은 Path.cwd() 여야 한다."""
    import sys as _sys
    from pathlib import Path

    captured = {}

    def fake_check(check_path=None):
        captured["check_path"] = check_path
        return {
            "can_run": True, "warning": "",
            "cuda_available": False, "mps_available": False,
            "demucs_device": "cpu",
            "ram_gb": 16.0, "vram_gb": 0.0, "free_space_gb": 100.0,
        }

    def fake_run(**kwargs):
        captured["base_dir"] = kwargs["base_dir"]
        return True

    monkeypatch.setattr(_sys, "argv", [
        "main.py", "--url", "https://youtu.be/x", "--sidecar",
    ])
    monkeypatch.setattr("src.app.main.check_hardware_compatibility", fake_check)
    monkeypatch.setattr("src.app.main.ensure_bundled_ffmpeg_on_path", lambda: None)
    monkeypatch.setattr("src.app.main.ensure_shared_ffmpeg_for_torchcodec", lambda: None)
    monkeypatch.setattr("src.app.main.run_pipeline", fake_run)

    from src.app.main import main
    main()

    assert captured["check_path"] == Path.cwd()
    assert captured["base_dir"] == Path.cwd()


def test_main_sidecar_emits_done_when_url_pipeline_succeeds(monkeypatch):
    """--sidecar --url 성공 경로는 done 이벤트로 끝나야 한다."""
    import io
    import sys as _sys

    buf = io.StringIO()
    monkeypatch.setattr(_sys, "__stdout__", buf)
    monkeypatch.setattr(
        _sys,
        "argv",
        ["main.py", "--url", "https://youtu.be/x", "--sidecar"],
    )
    monkeypatch.setattr(
        "src.app.main.check_hardware_compatibility",
        lambda check_path=None: {
            "can_run": True,
            "warning": "",
            "cuda_available": False,
            "mps_available": False,
            "demucs_device": "cpu",
            "ram_gb": 16.0,
            "vram_gb": 0.0,
            "free_space_gb": 100.0,
        },
    )
    monkeypatch.setattr("src.app.main.ensure_bundled_ffmpeg_on_path", lambda: None)
    monkeypatch.setattr("src.app.main.ensure_shared_ffmpeg_for_torchcodec", lambda: None)
    monkeypatch.setattr("src.app.main.run_pipeline", lambda **kwargs: True)

    from src.app.main import main

    main()

    lines = [json.loads(l) for l in buf.getvalue().strip().splitlines()]
    types = [e["type"] for e in lines]
    assert types[0] == "hardware"
    assert types[-1] == "done"
    assert lines[-1]["ok"] is True
