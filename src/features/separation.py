"""Stem separation via Demucs.

We call `demucs.separate.main(opts)` in-process so the sidecar runs a single
Python process (no subprocess of Python). To stream progress to the sidecar
emitter we monkey-patch `demucs.apply.tqdm` with a thin wrapper that yields
the same items but reports a 0..1 ratio per chunk.
"""
import contextlib
import shutil
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
    project_dir: Path,
    stems: Optional[str],
    device: str,
) -> List[str]:
    args = [
        "-n", "htdemucs",
        "-o", str(project_dir),
        "-d", device,
    ]
    if stems:
        args.extend(["--two-stems", stems])
    args.append(str(input_file))
    return args


def _move_to_stems(project_dir: Path, input_file: Path) -> dict[str, Path]:
    """Move demucs output from htdemucs/<title>/ to stems/ and return absolute paths."""
    track_stem = input_file.stem
    src_dir = project_dir / "htdemucs" / track_stem
    stems_dir = project_dir / "stems"
    stems_dir.mkdir(exist_ok=True)
    result: dict[str, Path] = {}
    for wav in src_dir.glob("*.wav"):
        dest = stems_dir / wav.name
        shutil.move(str(wav), str(dest))
        result[wav.stem] = dest.resolve()
    return result


def separate_audio(
    input_file: Path,
    project_dir: Path,
    stems: Optional[str] = None,
    device: str = "cpu",
    emitter: Optional[ProgressEmitter] = None,
) -> Optional[dict[str, Path]]:
    """Separate audio into stems using Meta's Demucs.

    Returns a dict of {stem_name: absolute_path} on success, None on failure.
    stage.done event is intentionally NOT emitted here; the caller (run_pipeline)
    emits it with the full project context (project_id, title, tracks).
    """
    if not input_file.exists():
        msg = f"오류: 입력 파일이 없습니다: {input_file}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(msg)
        return None

    if emitter is not None and emitter.enabled:
        emitter.emit("stage", stage="separate", status="start", model="htdemucs", device=device)
    else:
        print(f"분리 시작: {input_file.name}")
        print("하드웨어에 따라 시간이 오래 걸릴 수 있습니다...")

    opts = _build_demucs_args(input_file, project_dir, stems, device)

    try:
        from demucs.separate import main as demucs_main

        redirect_target = sys.stderr if (emitter is not None and emitter.enabled) else sys.stdout
        with _patched_demucs_progress(emitter), contextlib.redirect_stdout(redirect_target):
            demucs_main(opts)

        tracks = _move_to_stems(project_dir, input_file)
        return tracks

    except SystemExit as exc:
        msg = f"Demucs 종료 코드: {exc.code}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(f"오류: Demucs 프로세스가 실패했습니다. ({msg})")
        return None
    except Exception as e:
        msg = f"분리 중 예기치 않은 오류: {str(e)}"
        if emitter is not None and emitter.enabled:
            emitter.emit("error", stage="separate", message=msg)
        else:
            print(msg)
        return None
