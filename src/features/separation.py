import subprocess
import sys
from pathlib import Path
from typing import Optional


def separate_audio(
    input_file: Path,
    output_dir: Path,
    stems: Optional[str] = None,
    use_gpu: bool = False
) -> bool:
    """
    Separates audio into stems using Meta's Demucs.
    """
    if not input_file.exists():
        print(f"오류: 입력 파일이 없습니다: {input_file}")
        return False

    # Build demucs command
    # Default model is htdemucs
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "-o", str(output_dir),
        str(input_file)
    ]

    # Add specific stem filter if requested
    if stems:
        cmd.extend(["--two-stems", stems])

    # Force CPU if GPU is not available
    if not use_gpu:
        cmd.append("--cpu")

    try:
        print(f"분리 시작: {input_file.name}")
        print("하드웨어에 따라 시간이 오래 걸릴 수 있습니다...")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"분리가 완료되었습니다. 결과 경로: {output_dir}")
            return True
        print("오류: Demucs 프로세스가 실패했습니다.")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False

    except Exception as e:
        print(f"분리 중 예기치 않은 오류: {str(e)}")
        return False