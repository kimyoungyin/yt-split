from types import SimpleNamespace


def test_separate_audio_prints_subprocess_stderr_on_demucs_failure(
    monkeypatch, tmp_path, capsys
):
    """returncode != 0이면 Demucs가 stderr에 남긴 내용을 stdout에 그대로 노출해 사용자가 원인을 볼 수 있어야 한다."""
    input_file = tmp_path / "clip.mp3"
    input_file.touch()
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    err_text = "demucs-failed-unique-stderr-42"
    run_kwargs: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        run_kwargs.update(kwargs)
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=err_text,
        )

    monkeypatch.setattr("src.features.separation.subprocess.run", fake_run)

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, output_dir, stems=None, device="cuda")

    assert ok is False
    assert run_kwargs.get("capture_output") is True
    assert run_kwargs.get("text") is True
    captured = capsys.readouterr()
    assert err_text in captured.out


def test_separate_audio_prints_subprocess_stdout_when_stderr_empty_on_failure(
    monkeypatch, tmp_path, capsys
):
    """returncode != 0이고 stderr는 비어 있을 때, Demucs가 stdout에만 쓴 내용이면 그걸 보여야 한다."""
    input_file = tmp_path / "clip2.mp3"
    input_file.touch()
    output_dir = tmp_path / "out2"
    output_dir.mkdir()

    out_text = "demucs-only-stdout-diagnostic-99"

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=out_text,
            stderr="",
        )

    monkeypatch.setattr("src.features.separation.subprocess.run", fake_run)

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, output_dir, stems=None, device="cuda")

    assert ok is False
    captured = capsys.readouterr()
    assert out_text in captured.out


def test_separate_audio_prints_both_streams_when_both_set_on_failure(
    monkeypatch, tmp_path, capsys
):
    """실패 시 stderr와 stdout이 모두 비어 있지 않으면 둘 다 사용자에게 보여야 한다."""
    input_file = tmp_path / "clip3.mp3"
    input_file.touch()
    output_dir = tmp_path / "out3"
    output_dir.mkdir()

    err_part = "stderr-fragment-77"
    out_part = "stdout-fragment-88"

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=out_part,
            stderr=err_part,
        )

    monkeypatch.setattr("src.features.separation.subprocess.run", fake_run)

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, output_dir, stems=None, device="cuda")

    assert ok is False
    captured = capsys.readouterr()
    assert err_part in captured.out
    assert out_part in captured.out


def test_separate_audio_uses_demucs_device_cpu_when_device_cpu(monkeypatch, tmp_path):
    """Demucs 4.x: -d cpu로 CPU를 지정한다."""
    input_file = tmp_path / "cpu.mp3"
    input_file.touch()
    output_dir = tmp_path / "out_cpu"
    output_dir.mkdir()

    captured_cmd: list[str] | None = None

    def fake_run(cmd, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.features.separation.subprocess.run", fake_run)

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, output_dir, stems=None, device="cpu")

    assert ok is True
    assert captured_cmd is not None
    assert "--cpu" not in captured_cmd
    d_idx = captured_cmd.index("-d")
    assert captured_cmd[d_idx + 1] == "cpu"
