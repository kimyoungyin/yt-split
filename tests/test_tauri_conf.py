import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _current_triple() -> str:
    """현재 빌드 머신의 Rust target triple을 반환한다."""
    if sys.platform == "darwin":
        return (
            "aarch64-apple-darwin"
            if platform.machine() == "arm64"
            else "x86_64-apple-darwin"
        )
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    return (
        "aarch64-unknown-linux-gnu"
        if platform.machine() == "aarch64"
        else "x86_64-unknown-linux-gnu"
    )


def test_bundle_resources_includes_sidecar_triple():
    """bundle.resources가 현재 플랫폼 triple을 포함해야 한다."""
    conf = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text())
    resources = conf["bundle"]["resources"]
    assert resources, "bundle.resources가 비어 있어서는 안 된다"
    keys = resources if isinstance(resources, list) else list(resources.keys())
    triple = _current_triple()
    assert any(triple in k for k in keys), (
        f"{triple} 사이드카 경로 없음: {keys}"
    )


def test_build_sh_auto_patches_tauri_conf():
    """build.sh가 사이드카 스테이징 후 tauri.conf.json을 현재 플랫폼 triple로 패치해야 한다."""
    content = (ROOT / "pyinstaller" / "build.sh").read_text()
    assert "tauri.conf.json" in content, "build.sh에 tauri.conf.json 패치 코드가 없다"
    assert 'conf["bundle"]["resources"]' in content, (
        "build.sh 패치 코드가 Python json 모듈로 bundle.resources를 직접 수정하지 않는다"
    )


def test_spec_has_windows_ffmpeg_section():
    """yt-split-py.spec의 _ffmpeg_lib_dir()에 Windows FFmpeg DLL 수집 분기가 있어야 한다."""
    content = (ROOT / "pyinstaller" / "yt-split-py.spec").read_text()
    assert "win32" in content, "_ffmpeg_lib_dir()에 Windows(win32) 분기가 없다"
    assert ".dll" in content, "spec에 .dll 수집 코드가 없다"


def test_spec_has_linux_ldconfig_fallback():
    """yt-split-py.spec의 _ffmpeg_lib_dir()에 ldconfig -p fallback이 있어야 한다."""
    content = (ROOT / "pyinstaller" / "yt-split-py.spec").read_text()
    assert "ldconfig" in content, "_ffmpeg_lib_dir()에 ldconfig fallback이 없다"


def test_cancel_windows_uses_spawn_blocking_and_synchronize():
    """cancel_windows()가 tokio::spawn_blocking으로 감싸져 있고 SYNCHRONIZE 권한을 요청해야 한다."""
    content = (ROOT / "src-tauri" / "src" / "sidecar.rs").read_text()
    assert "spawn_blocking" in content, (
        "cancel_windows에 spawn_blocking이 없다 — WaitForSingleObject(5000)이 async 스레드를 블로킹한다"
    )
    assert "SYNCHRONIZE" in content, (
        "OpenProcess가 SYNCHRONIZE 권한을 요청하지 않는다 — WaitForSingleObject가 WAIT_FAILED를 반환한다"
    )


def test_build_ps1_uses_bom_free_utf8():
    """build.ps1의 tauri.conf.json 패치가 BOM-free UTF-8로 저장해야 한다."""
    content = (ROOT / "pyinstaller" / "build.ps1").read_text()
    assert "UTF8Encoding" in content or "utf8NoBOM" in content or "utf8nobom" in content.lower(), (
        "build.ps1이 Set-Content -Encoding UTF8를 사용하면 PowerShell 5.x에서 BOM이 포함된다"
    )


def test_bundle_resources_all_paths_exist():
    """bundle.resources에 나열된 경로는 모두 실제로 존재해야 한다 (빌드 실패 방지)."""
    conf = json.loads(
        (Path(__file__).parents[1] / "src-tauri" / "tauri.conf.json").read_text()
    )
    resources = conf["bundle"]["resources"]
    tauri_dir = Path(__file__).parents[1] / "src-tauri"
    keys = resources if isinstance(resources, list) else list(resources.keys())
    missing = [k for k in keys if not (tauri_dir / k).exists()]
    assert not missing, f"존재하지 않는 resource 경로: {missing}"
