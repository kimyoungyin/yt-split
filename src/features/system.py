import shutil
import torch
import psutil
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_demucs_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def check_hardware_compatibility(check_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    하드웨어 사양을 체크하고 실행 가능 여부를 반환합니다.
    check_path: 디스크 여유 공간을 확인할 경로 (기본값: 현재 작업 디렉터리)
    """
    if check_path is None:
        check_path = Path.cwd()
    cuda_available = torch.cuda.is_available()
    mps_mod = getattr(torch.backends, "mps", None)
    mps_available = bool(
        mps_mod is not None and mps_mod.is_available()
    )
    demucs_device = _resolve_demucs_device()

    stats: Dict[str, Any] = {
        "cuda_available": cuda_available,
        "mps_available": mps_available,
        "demucs_device": demucs_device,
        "vram_gb": 0.0,
        "ram_gb": psutil.virtual_memory().total / (1024**3),
        "free_space_gb": shutil.disk_usage(check_path).free / (1024**3),
        "can_run": True,
        "warning": "",
    }

    if cuda_available and torch.cuda.device_count() > 0:
        stats["vram_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)

    if demucs_device == "cpu":
        stats["warning"] = (
            "경고: GPU 가속(CUDA/MPS)을 사용할 수 없습니다. "
            "CPU 모드는 연산 속도가 매우 느릴 수 있습니다."
        )

    if stats["ram_gb"] < 8:
        stats["warning"] += "\n경고: 시스템 RAM이 8GB 미만입니다. 메모리 부족으로 종료될 수 있습니다."

    if stats["free_space_gb"] < 5:
        stats["can_run"] = False
        stats["warning"] += "\n에러: 디스크 공간이 부족합니다 (최소 5GB 필요)."

    return stats
