import argparse
import sys
from pathlib import Path
from typing import Optional

from src.features.download import download_audio
from src.features.ffmpeg_env import (
    ensure_bundled_ffmpeg_on_path,
    ensure_shared_ffmpeg_for_torchcodec,
)
from src.features.separation import separate_audio
from src.features.system import check_hardware_compatibility


def run_pipeline(
    url: str,
    stem: Optional[str],
    device: str,
    base_dir: Path,
) -> bool:
    """Download audio from URL then run stem separation. Returns True on success."""
    downloads_dir = base_dir / "downloads"
    output_dir = base_dir / "output"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = download_audio(url, downloads_dir)
    if downloaded is None:
        return False

    return separate_audio(downloaded, output_dir, stem, device)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Audio Separator")
    parser.add_argument("--url", type=str, help="YouTube URL to process")
    parser.add_argument("--check", action="store_true", help="Check system hardware")
    parser.add_argument("--stem", type=str, choices=["vocals", "drums", "bass", "other"], help="Target specific stem")

    args = parser.parse_args()

    stats = check_hardware_compatibility()

    if args.check:
        print("--- Hardware Status ---")
        print(f"CUDA: {stats['cuda_available']}")
        print(f"MPS: {stats['mps_available']}")
        print(f"Demucs device: {stats['demucs_device']}")
        print(f"RAM: {stats['ram_gb']:.2f} GB")
        if stats['warning']:
            print(f"Messages: {stats['warning']}")
        return

    if not stats["can_run"]:
        print(f"실행 불가: {stats['warning']}")
        sys.exit(1)

    if stats["warning"]:
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
        )
        if not ok:
            print(
                "처리 실패: 다운로드 또는 분리 단계에서 오류가 발생했습니다.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
