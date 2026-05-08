import json
from pathlib import Path


def test_bundle_resources_includes_sidecar_triple():
    """bundle.resources가 비어 있지 않고 aarch64-apple-darwin 사이드카 경로를 포함해야 한다."""
    conf = json.loads(
        (Path(__file__).parents[1] / "src-tauri" / "tauri.conf.json").read_text()
    )
    resources = conf["bundle"]["resources"]
    assert resources, "bundle.resources가 비어 있어서는 안 된다"
    keys = resources if isinstance(resources, list) else list(resources.keys())
    assert any("yt-split-py-aarch64-apple-darwin" in k for k in keys), (
        f"aarch64-apple-darwin 사이드카 경로 없음: {keys}"
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
