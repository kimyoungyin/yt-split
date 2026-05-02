import argparse
import sys
from pathlib import Path
from typing import Optional

from src.features.download import download_audio
from src.features.ffmpeg_env import (
    ensure_bundled_ffmpeg_on_path,
    ensure_shared_ffmpeg_for_torchcodec,
)
from src.features.progress import ProgressEmitter
from src.features.separation import separate_audio
from src.features.system import check_hardware_compatibility


def run_pipeline(
    url: str,
    stem: Optional[str],
    device: str,
    base_dir: Path,
    emitter: Optional[ProgressEmitter] = None,
) -> bool:
    """Download audio from URL then run stem separation. Returns True on success."""
    downloads_dir = base_dir / "downloads"
    output_dir = base_dir / "output"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = download_audio(url, downloads_dir, emitter=emitter)
    if downloaded is None:
        return False

    return separate_audio(downloaded, output_dir, stem, device, emitter=emitter)


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

    args = parser.parse_args()
    emitter = ProgressEmitter(enabled=bool(args.sidecar))

    stats = check_hardware_compatibility(check_path=Path.cwd())

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
            base_dir=Path.cwd(),
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
