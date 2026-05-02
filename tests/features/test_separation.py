"""Tests for the in-process Demucs separation wrapper."""
from pathlib import Path
from typing import List, Optional

import pytest


def _make_track_outputs(output_dir: Path, track_stem: str) -> None:
    """Create the file layout demucs would produce after a successful run."""
    track_dir = output_dir / "htdemucs" / track_stem
    track_dir.mkdir(parents=True, exist_ok=True)
    for stem in ("vocals", "drums", "bass", "other"):
        (track_dir / f"{stem}.wav").write_bytes(b"\x00\x00")


def test_separate_audio_returns_false_when_input_missing(tmp_path, capsys):
    from src.features.separation import separate_audio

    missing = tmp_path / "missing.mp3"
    out = tmp_path / "out"
    out.mkdir()

    ok = separate_audio(missing, out, stems=None, device="cpu")

    assert ok is False
    assert "입력 파일이 없습니다" in capsys.readouterr().out


def test_separate_audio_passes_expected_args_to_demucs_main(monkeypatch, tmp_path):
    """demucs.separate.main is called with -n htdemucs, -o, -d, and the input file."""
    captured: List[str] = []

    def fake_main(opts):
        captured.extend(opts)
        _make_track_outputs(tmp_path / "out", "song")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "song.mp3"
    input_file.write_bytes(b"\x00\x00")
    out = tmp_path / "out"
    out.mkdir()

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, out, stems=None, device="mps")

    assert ok is True
    assert "-n" in captured and captured[captured.index("-n") + 1] == "htdemucs"
    assert "-o" in captured and captured[captured.index("-o") + 1] == str(out)
    assert "-d" in captured and captured[captured.index("-d") + 1] == "mps"
    assert str(input_file) in captured


def test_separate_audio_appends_two_stems_when_stem_set(monkeypatch, tmp_path):
    captured: List[str] = []

    def fake_main(opts):
        captured.extend(opts)
        _make_track_outputs(tmp_path / "out", "clip")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "clip.mp3"
    input_file.write_bytes(b"\x00\x00")
    out = tmp_path / "out"
    out.mkdir()

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, out, stems="vocals", device="cpu")

    assert ok is True
    assert "--two-stems" in captured
    assert captured[captured.index("--two-stems") + 1] == "vocals"


def test_separate_audio_returns_false_on_systemexit(monkeypatch, tmp_path, capsys):
    """demucs.separate uses dora.log.fatal which calls sys.exit on errors."""
    def fake_main(opts):
        raise SystemExit(1)

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "bad.mp3"
    input_file.write_bytes(b"\x00\x00")
    out = tmp_path / "out"
    out.mkdir()

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, out, stems=None, device="cpu")

    assert ok is False
    assert "Demucs" in capsys.readouterr().out


def test_separate_audio_returns_false_on_unexpected_exception(monkeypatch, tmp_path, capsys):
    def fake_main(opts):
        raise RuntimeError("model load failed")

    monkeypatch.setattr("demucs.separate.main", fake_main)

    input_file = tmp_path / "boom.mp3"
    input_file.write_bytes(b"\x00\x00")
    out = tmp_path / "out"
    out.mkdir()

    from src.features.separation import separate_audio

    ok = separate_audio(input_file, out, stems=None, device="cpu")

    assert ok is False
    assert "model load failed" in capsys.readouterr().out


def test_separate_audio_emits_start_and_done_when_emitter_enabled(monkeypatch, tmp_path):
    def fake_main(opts):
        _make_track_outputs(tmp_path / "out", "clip")

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
    out = tmp_path / "out"
    out.mkdir()

    ok = separate_audio(input_file, out, stems=None, device="cpu", emitter=CapturingEmitter())

    assert ok is True
    starts = [e for e in events if e["type"] == "stage" and e.get("status") == "start"]
    dones = [e for e in events if e["type"] == "stage" and e.get("status") == "done"]
    assert starts and dones
    assert dones[0]["tracks"]
    assert "vocals" in dones[0]["tracks"]


def test_separate_audio_progress_tqdm_patch_emits_progress_events(monkeypatch, tmp_path):
    """The patched tqdm wrapper inside demucs.apply emits 'progress' events on iter."""
    def fake_main(opts):
        # Simulate demucs.apply.apply_model's use of tqdm: iterate over a list of futures.
        from demucs import apply as demucs_apply
        for _ in demucs_apply.tqdm.tqdm([1, 2, 3, 4], unit_scale=1, ncols=80, unit='s'):
            pass
        _make_track_outputs(tmp_path / "out", "clip")

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
    out = tmp_path / "out"
    out.mkdir()

    ok = separate_audio(input_file, out, stems=None, device="cpu", emitter=CapturingEmitter())

    assert ok is True
    progress = [e for e in events if e["type"] == "progress" and e.get("stage") == "separate"]
    assert progress, "expected at least one separate progress event"
    assert progress[-1]["value"] == 1.0
