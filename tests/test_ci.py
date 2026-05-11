import pathlib

import yaml

ROOT = pathlib.Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _load_yaml(path: pathlib.Path):
    with open(path) as f:
        return yaml.safe_load(f)


def _workflow_triggers(workflow: dict):
    # PyYAML treats the YAML 1.1 key "on" as a boolean unless quoted.
    return workflow.get("on") or workflow.get(True) or {}


def test_build_workflow_exists():
    assert WORKFLOW.exists(), f"{WORKFLOW} not found"


def test_build_workflow_uses_supported_release_matrix():
    wf = _load_yaml(WORKFLOW)
    runners = [job["os"] for job in wf["jobs"]["build"]["strategy"]["matrix"]["include"]]
    assert runners == ["macos-14", "ubuntu-22.04", "windows-latest"]
    assert "macos-13" not in runners


def test_build_workflow_is_reusable_by_release_workflow():
    wf = _load_yaml(WORKFLOW)
    triggers = _workflow_triggers(wf)
    assert "workflow_call" in triggers, "release.yml이 재사용할 workflow_call 트리거가 없다"


def test_build_workflow_has_cache_steps():
    wf = _load_yaml(WORKFLOW)
    step_uses = [s.get("uses", "") for s in wf["jobs"]["build"]["steps"]]
    assert any("actions/cache" in u for u in step_uses), "캐시 step 없음"


def test_build_workflow_has_artifact_upload():
    wf = _load_yaml(WORKFLOW)
    step_uses = [s.get("uses", "") for s in wf["jobs"]["build"]["steps"]]
    assert any("actions/upload-artifact" in u for u in step_uses), "artifact upload step 없음"


def test_artifact_upload_fails_when_expected_bundle_is_missing():
    wf = _load_yaml(WORKFLOW)
    upload = next(
        s
        for s in wf["jobs"]["build"]["steps"]
        if "actions/upload-artifact" in s.get("uses", "")
    )
    assert upload["with"].get("if-no-files-found") == "error", (
        "artifact가 없을 때 ignore하면 Windows처럼 빈 성공이 발생한다"
    )


def test_release_workflow_reuses_build_workflow_before_publishing():
    wf = _load_yaml(RELEASE_WORKFLOW)
    triggers = _workflow_triggers(wf)
    assert triggers["push"]["tags"] == ["v*.*.*"]

    build_job = wf["jobs"]["build"]
    assert build_job["uses"] == "./.github/workflows/build.yml"

    release_job = wf["jobs"]["release"]
    assert release_job["needs"] == "build"
    step_uses = [s.get("uses", "") for s in release_job["steps"]]
    assert any("actions/download-artifact" in u for u in step_uses), (
        "release job이 reusable build artifact를 다운로드하지 않는다"
    )
    assert any("softprops/action-gh-release" in u for u in step_uses), (
        "release job이 GitHub Release에 asset을 첨부하지 않는다"
    )


def test_release_workflow_fails_on_unmatched_release_assets():
    wf = _load_yaml(RELEASE_WORKFLOW)
    release_job = wf["jobs"]["release"]
    upload = next(
        s
        for s in release_job["steps"]
        if "softprops/action-gh-release" in s.get("uses", "")
    )
    assert upload["with"].get("fail_on_unmatched_files") is True, (
        "release asset glob이 빗나가면 GitHub Release가 빈 성공으로 끝나면 안 된다"
    )
    files = upload["with"]["files"]
    assert "release-assets/**/*.dmg" in files
    assert "release-assets/**/*.exe" in files
    assert "release-assets/**/*.msi" in files
    assert "release-assets/**/*.deb" in files
    assert "appimage" not in files.lower()
    assert ".rpm" not in files.lower()


def test_build_scripts_patch_platform_bundle_targets():
    build_sh = (ROOT / "pyinstaller" / "build.sh").read_text()
    build_ps1 = (ROOT / "pyinstaller" / "build.ps1").read_text()

    assert 'BUNDLE_TARGETS=\'["dmg"]\'' in build_sh, (
        "macOS build.sh는 dmg만 bundle target으로 설정해야 한다"
    )
    assert 'BUNDLE_TARGETS=\'["deb"]\'' in build_sh, (
        "Linux build.sh는 AppImage/RPM 대신 deb만 bundle target으로 설정해야 한다"
    )
    assert 'conf["bundle"]["targets"] = ${BUNDLE_TARGETS}' in build_sh

    assert '$BUNDLE_TARGETS = @("nsis", "msi")' in build_ps1, (
        "Windows build.ps1은 nsis와 msi를 bundle target으로 설정해야 한다"
    )
    assert "$conf.bundle.targets = $BUNDLE_TARGETS" in build_ps1


def test_build_workflow_pip_cache_uses_setup_python_builtin():
    """수동 pip cache step 대신 setup-python의 cache: pip 파라미터를 사용해야 한다.
    플랫폼별 pip cache 경로가 달라 수동 ~//.cache/pip는 macOS/Windows에서 미적중한다."""
    wf = _load_yaml(WORKFLOW)
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


def test_build_workflow_uses_rust_cache_action():
    """Rust cache는 platform-aware action으로 관리해 OS별 target cache 충돌을 피한다."""
    wf = _load_yaml(WORKFLOW)
    steps = wf["jobs"]["build"]["steps"]
    rust_cache = next(
        s for s in steps if "swatinem/rust-cache" in s.get("uses", "")
    )
    assert rust_cache.get("with", {}).get("workspaces") == "src-tauri -> target"
