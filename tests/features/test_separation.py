"""Tests for the in-process Demucs separation wrapper."""
from pathlib import Path
from typing import List, Optional

import pytest


def _make_track_outputs(project_dir: Path, track_stem: str) -> None:
    """Create the file layout demucs would produce under project_dir."""
    track_dir = project_dir / "htdemucs" / track_stem
    track_dir.mkdir(parents=True, exist_ok=True)
    for stem in ("vocals", "drums", "bass", "other"):
        (track_dir / f"{stem}.wav").write_bytes(b"\x00\x00")


def test_separate_audio_returns_none_when_input_missing(tmp_path, capsys):
    from src.features.separation import separate_audio

    missing = tmp_path / "missing.mp3"
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    result = separate_audio(missing, project_dir, stems=None, device="cpu")

    assert result is None
    assert "입력 파일이 없습니다" in capsys.readouterr().out


def test_separate_audio_passes_expected_args_to_demucs_main(monkeypatch, tmp_path):
    """demucs.separate.main is called with -n htdemucs, -o, -d, and the input file."""
    captured: List[str] = []
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    def fake_main(opts):
        captured.extend(opts)
        _make_track_outputs(project_dir, "song")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "song.mp3"
    input_file.write_bytes(b"\x00\x00")

    from src.features.separation import separate_audio

    result = separate_audio(input_file, project_dir, stems=None, device="mps")

    assert result is not None
    assert "-n" in captured and captured[captured.index("-n") + 1] == "htdemucs"
    assert "-o" in captured and captured[captured.index("-o") + 1] == str(project_dir)
    assert "-d" in captured and captured[captured.index("-d") + 1] == "mps"
    assert str(input_file) in captured
    assert "vocals" in result


def test_separate_audio_appends_two_stems_when_stem_set(monkeypatch, tmp_path):
    captured: List[str] = []
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    def fake_main(opts):
        captured.extend(opts)
        _make_track_outputs(project_dir, "clip")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "clip.mp3"
    input_file.write_bytes(b"\x00\x00")

    from src.features.separation import separate_audio

    result = separate_audio(input_file, project_dir, stems="vocals", device="cpu")

    assert result is not None
    assert "--two-stems" in captured
    assert captured[captured.index("--two-stems") + 1] == "vocals"


def test_separate_audio_returns_none_on_systemexit(monkeypatch, tmp_path, capsys):
    """demucs.separate uses dora.log.fatal which calls sys.exit on errors."""
    def fake_main(opts):
        raise SystemExit(1)

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "bad.mp3"
    input_file.write_bytes(b"\x00\x00")
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    from src.features.separation import separate_audio

    result = separate_audio(input_file, project_dir, stems=None, device="cpu")

    assert result is None
    assert "Demucs" in capsys.readouterr().out


def test_separate_audio_returns_none_on_unexpected_exception(monkeypatch, tmp_path, capsys):
    def fake_main(opts):
        raise RuntimeError("model load failed")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "boom.mp3"
    input_file.write_bytes(b"\x00\x00")
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    from src.features.separation import separate_audio

    result = separate_audio(input_file, project_dir, stems=None, device="cpu")

    assert result is None
    assert "model load failed" in capsys.readouterr().out


def test_separate_audio_emits_start_when_emitter_enabled(monkeypatch, tmp_path):
    """separate_audio는 stage.start를 emit한다. stage.done은 호출부(run_pipeline)에서 처리."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    def fake_main(opts):
        _make_track_outputs(project_dir, "clip")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    from src.features.progress import ProgressEmitter
    from src.features.separation import separate_audio

    events: List[dict] = []

    class CapturingEmitter(ProgressEmitter):
        def __init__(self):
            super().__init__(enabled=True)

        def emit(self, type, **fields):
            events.append({"type": type, **fields})

    input_file = tmp_path / "clip.mp3"
    input_file.write_bytes(b"\x00\x00")

    result = separate_audio(input_file, project_dir, stems=None, device="cpu", emitter=CapturingEmitter())

    assert result is not None
    assert "vocals" in result
    starts = [e for e in events if e["type"] == "stage" and e.get("status") == "start"]
    assert starts, "stage.start event expected"
    dones = [e for e in events if e["type"] == "stage" and e.get("status") == "done"]
    assert not dones, "stage.done must NOT be emitted by separate_audio (moved to run_pipeline)"


def test_separate_audio_progress_tqdm_patch_emits_progress_events(monkeypatch, tmp_path):
    """The patched tqdm wrapper inside demucs.apply emits 'progress' events on iter."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    def fake_main(opts):
        from demucs import apply as demucs_apply
        for _ in demucs_apply.tqdm.tqdm([1, 2, 3, 4], unit_scale=1, ncols=80, unit='s'):
            pass
        _make_track_outputs(project_dir, "clip")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    from src.features.progress import ProgressEmitter
    from src.features.separation import separate_audio

    events: List[dict] = []

    class CapturingEmitter(ProgressEmitter):
        def __init__(self):
            super().__init__(enabled=True)

        def emit(self, type, **fields):
            events.append({"type": type, **fields})

    input_file = tmp_path / "clip.mp3"
    input_file.write_bytes(b"\x00\x00")

    result = separate_audio(input_file, project_dir, stems=None, device="cpu", emitter=CapturingEmitter())

    assert result is not None
    progress = [e for e in events if e["type"] == "progress" and e.get("stage") == "separate"]
    assert progress, "expected at least one separate progress event"
    assert progress[-1]["value"] == 1.0
