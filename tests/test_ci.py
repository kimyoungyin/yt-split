import pathlib

import yaml

ROOT = pathlib.Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"


def test_build_workflow_exists():
    assert WORKFLOW.exists(), f"{WORKFLOW} not found"


def test_build_workflow_has_four_matrix_runners():
    with open(WORKFLOW) as f:
        wf = yaml.safe_load(f)
    runners = [job["os"] for job in wf["jobs"]["build"]["strategy"]["matrix"]["include"]]
    assert "macos-14" in runners
    assert "macos-13" in runners
    assert "ubuntu-22.04" in runners
    assert "windows-latest" in runners


def test_build_workflow_has_cache_steps():
    with open(WORKFLOW) as f:
        wf = yaml.safe_load(f)
    step_uses = [s.get("uses", "") for s in wf["jobs"]["build"]["steps"]]
    assert any("actions/cache" in u for u in step_uses), "캐시 step 없음"


def test_build_workflow_has_artifact_upload():
    with open(WORKFLOW) as f:
        wf = yaml.safe_load(f)
    step_uses = [s.get("uses", "") for s in wf["jobs"]["build"]["steps"]]
    assert any("actions/upload-artifact" in u for u in step_uses), "artifact upload step 없음"


def test_build_workflow_pip_cache_uses_setup_python_builtin():
    """수동 pip cache step 대신 setup-python의 cache: pip 파라미터를 사용해야 한다.
    플랫폼별 pip cache 경로가 달라 수동 ~//.cache/pip는 macOS/Windows에서 미적중한다."""
    with open(WORKFLOW) as f:
        wf = yaml.safe_load(f)
    steps = wf["jobs"]["build"]["steps"]
    setup_python = next(s for s in steps if "setup-python" in s.get("uses", ""))
    assert setup_python.get("with", {}).get("cache") == "pip", (
        "setup-python에 cache: pip 파라미터 없음 — 플랫폼별 pip cache 경로를 자동 처리하지 못함"
    )
    # 수동 pip cache step이 없어야 한다 (setup-python builtin이 대체함)
    manual_pip_cache = [
        s for s in steps
        if "actions/cache" in s.get("uses", "")
        and "pip" in s.get("with", {}).get("path", "")
    ]
    assert len(manual_pip_cache) == 0, "수동 pip cache step이 남아 있음 — setup-python cache: pip와 중복"


def test_build_workflow_cargo_cache_has_restore_keys():
    """Cargo.lock이 변경될 때 partial cache reuse를 위해 restore-keys가 있어야 한다."""
    with open(WORKFLOW) as f:
        wf = yaml.safe_load(f)
    steps = wf["jobs"]["build"]["steps"]
    cargo_cache = next(
        s for s in steps
        if "actions/cache" in s.get("uses", "")
        and "cargo" in s.get("with", {}).get("path", "")
    )
    restore_keys = cargo_cache.get("with", {}).get("restore-keys", "")
    assert restore_keys, "cargo cache에 restore-keys 없음"
    assert "runner.os" in restore_keys, "restore-keys에 runner.os가 없어 OS간 캐시 충돌 가능"
