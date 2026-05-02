"""Stem separation via Demucs.

We call `demucs.separate.main(opts)` in-process so the sidecar runs a single
Python process (no subprocess of Python). To stream progress to the sidecar
emitter we monkey-patch `demucs.apply.tqdm` with a thin wrapper that yields
the same items but reports a 0..1 ratio per chunk.
"""
import contextlib
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Optional

from src.features.progress import ProgressEmitter


class _ProgressTqdm:
    """Drop-in replacement for tqdm.tqdm used inside demucs.apply.

    demucs.apply.py invokes `tqdm.tqdm(futures, unit_scale=..., ncols=..., unit=...)`
    and iterates it. We just need an iterable wrapper that emits a progress
    ratio between 0 and 1 as it advances.
    """

    def __init__(self, iterable: Iterable[Any], **_kwargs: Any) -> None:
        self._items: List[Any] = list(iterable)
        self._total: int = len(self._items)
        self._emitter: Optional[ProgressEmitter] = _current_emitter

    def __iter__(self) -> Iterator[Any]:
        total = self._total or 1
        for i, item in enumerate(self._items):
            if self._emitter is not None:
                self._emitter.emit("progress", stage="separate", value=i / total)
            yield item
        if self._emitter is not None:
            self._emitter.emit("progress", stage="separate", value=1.0)


_current_emitter: Optional[ProgressEmitter] = None


@contextlib.contextmanager
def _patched_demucs_progress(emitter: Optional[ProgressEmitter]) -> Iterator[None]:
    """Patch demucs.apply.tqdm so iteration emits NDJSON progress events.

    Imports demucs lazily so users running --check don't pay the heavy import.
    """
    global _current_emitter
    from demucs import apply as demucs_apply

    original_tqdm = demucs_apply.tqdm
    fake_tqdm_module = type("_PatchedTqdm", (), {"tqdm": _ProgressTqdm})
    demucs_apply.tqdm = fake_tqdm_module
    _current_emitter = emitter
    try:
        yield
    finally:
        demucs_apply.tqdm = original_tqdm
        _current_emitter = None


def _build_demucs_args(
    input_file: Path,
    output_dir: Path,
    stems: Optional[str],
    device: str,
) -> List[str]:
    args = [
        "-n", "htdemucs",
        "-o", str(output_dir),
        "-d", device,
    ]
    if stems:
        args.extend(["--two-stems", stems])
    args.append(str(input_file))
    return args


def _resolve_output_tracks(
    output_dir: Path,
    input_file: Path,
    stems: Optional[str],
) -> dict[str, str]:
    """Map demucs output filenames to a {stem_name: absolute_path} dict.

    demucs writes to `<output_dir>/htdemucs/<track_stem>/<stem>.wav`.
    """
    track_stem = input_file.stem
    track_dir = output_dir / "htdemucs" / track_stem
    if not track_dir.is_dir():
        return {}
    return {
        wav.stem: str(wav.resolve())
        for wav in track_dir.glob("*.wav")
    }


def separate_audio(
    input_file: Path,
    output_dir: Path,
    stems: Optional[str] = None,
    device: str = "cpu",
    emitter: Optional[ProgressEmitter] = None,
) -> bool:
    """Separates audio into stems using Meta's Demucs.

    `device` is forwarded to demucs as `-d` (cpu, cuda, mps).
    `emitter` reports progress events; pass None to silence (CLI mode).
    """
    if not input_file.exists():
        msg = f"오류: 입력 파일이 없습니다: {input_file}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(msg)
        return False

    if emitter is not None and emitter.enabled:
        emitter.emit("stage", stage="separate", status="start", model="htdemucs", device=device)
    else:
        print(f"분리 시작: {input_file.name}")
        print("하드웨어에 따라 시간이 오래 걸릴 수 있습니다...")

    opts = _build_demucs_args(input_file, output_dir, stems, device)

    try:
        from demucs.separate import main as demucs_main

        # Demucs prints status lines to stdout. In sidecar mode stdout is the
        # NDJSON channel, so redirect demucs prints to stderr.
        redirect_target = sys.stderr if (emitter is not None and emitter.enabled) else sys.stdout
        with _patched_demucs_progress(emitter), contextlib.redirect_stdout(redirect_target):
            demucs_main(opts)

        tracks = _resolve_output_tracks(output_dir, input_file, stems)
        if emitter is not None and emitter.enabled:
            emitter.emit("stage", stage="separate", status="done", tracks=tracks)
        else:
            print(f"분리가 완료되었습니다. 결과 경로: {output_dir}")
        return True

    except SystemExit as exc:
        # demucs.separate uses dora.log.fatal which calls sys.exit on errors.
        msg = f"Demucs 종료 코드: {exc.code}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(f"오류: Demucs 프로세스가 실패했습니다. ({msg})")
        return False
    except Exception as e:
        msg = f"분리 중 예기치 않은 오류: {str(e)}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(msg)
        return False
