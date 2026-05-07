import argparse
import signal
import sys
import uuid as _uuid
from pathlib import Path
from types import FrameType
from typing import Optional

from src.features.download import download_audio
from src.features.ffmpeg_env import (
    ensure_bundled_ffmpeg_on_path,
    ensure_shared_ffmpeg_for_torchcodec,
)
from src.features.progress import ProgressEmitter
from src.features.project import create_project_metadata
from src.features.separation import separate_audio
from src.features.system import check_hardware_compatibility


def _install_cancel_handler(emitter: ProgressEmitter) -> None:
    """SIGTERM from Tauri's cancel_pipeline → emit a final error+done pair so
    the UI can distinguish 'cancelled' from a generic non-zero exit, then exit.

    Windows lacks SIGTERM as a sendable signal; we still register if the
    constant exists, since the cancel command on Windows is a Phase 4 follow-up.
    """
    sigterm = getattr(signal, "SIGTERM", None)
    if sigterm is None:
        return

    def _on_term(signum: int, _frame: Optional[FrameType]) -> None:
        try:
            emitter.emit(
                "error",
                stage="pipeline",
                message="사용자가 분리를 취소했습니다.",
            )
            emitter.emit("done", ok=False)
        finally:
            sys.exit(128 + signum)

    signal.signal(sigterm, _on_term)


def run_pipeline(
    url: str,
    stem: Optional[str],
    device: str,
    base_dir: Path,
    emitter: Optional[ProgressEmitter] = None,
) -> bool:
    """Download audio from URL, run stem separation, write project metadata."""
    downloads_dir = base_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    downloaded, title = download_audio(url, downloads_dir, emitter=emitter)
    if downloaded is None:
        return False

    project_id = str(_uuid.uuid4())
    project_dir = base_dir / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    tracks = separate_audio(downloaded, project_dir, stem, device, emitter=emitter)
    if tracks is None:
        return False

    create_project_metadata(
        base=base_dir,
        project_id=project_id,
        title=title,
        url=url,
        device=device,
        stem_mode=stem or "all",
        tracks=tracks,
    )

    if emitter is not None and emitter.enabled:
        emitter.emit(
            "stage", stage="separate", status="done",
            project_id=project_id, title=title,
            tracks={k: str(v) for k, v in tracks.items()},
        )
    else:
        print(f"분리 완료: {project_dir}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Audio Separator")
    parser.add_argument("--url", type=str, help="YouTube URL to process")
    parser.add_argument("--check", action="store_true", help="Check system hardware")
    parser.add_argument("--stem", type=str, choices=["vocals", "drums", "bass", "other"], help="Target specific stem")
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help="Emit NDJSON events on stdout for the Tauri host (no human-readable prints).",
    )
    parser.add_argument(
        "--workdir",
        type=str,
        help="Base directory for downloads and projects (default: cwd).",
    )

    args = parser.parse_args()
    base_dir = Path(args.workdir) if args.workdir else Path.cwd()
    emitter = ProgressEmitter(enabled=bool(args.sidecar))

    if emitter.enabled:
        _install_cancel_handler(emitter)

    stats = check_hardware_compatibility(check_path=base_dir)

    if emitter.enabled:
        emitter.emit(
            "hardware",
            cuda_available=stats["cuda_available"],
            mps_available=stats["mps_available"],
            demucs_device=stats["demucs_device"],
            ram_gb=stats["ram_gb"],
            vram_gb=stats["vram_gb"],
            free_space_gb=stats["free_space_gb"],
            can_run=stats["can_run"],
            warning=stats["warning"],
        )

    if args.check:
        if not emitter.enabled:
            print("--- Hardware Status ---")
            print(f"CUDA: {stats['cuda_available']}")
            print(f"MPS: {stats['mps_available']}")
            print(f"Demucs device: {stats['demucs_device']}")
            print(f"RAM: {stats['ram_gb']:.2f} GB")
            if stats['warning']:
                print(f"Messages: {stats['warning']}")
        return

    if not stats["can_run"]:
        msg = f"실행 불가: {stats['warning']}"
        if emitter.enabled:
            emitter.emit("error", stage="system", message=msg)
        else:
            print(msg)
        sys.exit(1)

    if stats["warning"] and not emitter.enabled:
        print(stats["warning"])
        confirm = input("계속 진행하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit(0)

    if args.url:
        ensure_bundled_ffmpeg_on_path()
        ensure_shared_ffmpeg_for_torchcodec()
        ok = run_pipeline(
            url=args.url,
            stem=args.stem,
            device=stats["demucs_device"],
            base_dir=base_dir,
            emitter=emitter,
        )
        if not ok:
            if emitter.enabled:
                emitter.emit(
                    "error",
                    stage="pipeline",
                    message="처리 실패: 다운로드 또는 분리 단계에서 오류가 발생했습니다.",
                )
            else:
                print(
                    "처리 실패: 다운로드 또는 분리 단계에서 오류가 발생했습니다.",
                    file=sys.stderr,
                )
            sys.exit(1)
        if emitter.enabled:
            emitter.emit("done", ok=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
