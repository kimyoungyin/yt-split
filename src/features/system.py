import torch
import psutil
import shutil
from typing import Dict, Any

def check_hardware_compatibility() -> Dict[str, Any]:
    """
    하드웨어 사양을 체크하고 실행 가능 여부를 반환합니다.
    """
    stats = {
        "cuda_available": torch.cuda.is_available(),
        "vram_gb": 0.0,
        "ram_gb": psutil.virtual_memory().total / (1024**3),
        "free_space_gb": shutil.disk_usage(".").free / (1024**3),
        "can_run": True,
        "warning": ""
    }

    if stats["cuda_available"]:
        stats["vram_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    else:
        stats["warning"] = "경고: GPU(CUDA)를 사용할 수 없습니다. CPU 모드는 연산 속도가 매우 느립니다."
    
    if stats["ram_gb"] < 8:
        stats["warning"] += "\n경고: 시스템 RAM이 8GB 미만입니다. 메모리 부족으로 종료될 수 있습니다."
    
    if stats["free_space_gb"] < 5:
        stats["can_run"] = False
        stats["warning"] += "\n에러: 디스크 공간이 부족합니다 (최소 5GB 필요)."

    return stats