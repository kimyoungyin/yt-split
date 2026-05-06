# 프로젝트 라이브러리 + AppLocalData + 출력 경로 정리 — Phase 3 (Master Plan)

> **상태:** Draft v0.1 (master plan, 다른 AI 리뷰를 받아가며 수정한다)
> **선행:** [Phase 1](./phase-1.md), [Phase 2](./phase-2.md)
> **다음:** [Phase 4 — 패키징 / Phase 5 — CI](./roadmap.md)

이 문서는 Phase 3의 마스터 플랜이다. Phase 2와 동일한 구조(Context → 결정 → 디렉터리 → 슬라이스 → 검증 → Quirks)를 사용하되, 슬라이스 단위(P3-A ~ P3-D)로 쪼개 각 슬라이스가 독립적인 `/pwrc-plan → /pwrc-work → /pwrc-review` 사이클로 돌 수 있게 한다. Open decisions 섹션은 리뷰 라운드 후 채워 넣는다.

---

## Context

Phase 1·2는 **단일 곡 워크플로우**만 본다. 사이드카가 끝나면 `usePipelineStore.tracks`로 4개 stem 절대경로가 들어오고 Player가 그 dict를 받아 동시 재생한다. 그러나:

1. **출력 경로가 워크스페이스 루트(`./output/`, `./downloads/`)에 박혀 있다.** Phase 1에서 `current_dir = workspace_root`로 고정한 것은 dev 편의 결정이었고 ([phase-1.md](./phase-1.md), [sidecar.rs:107-110](../src-tauri/src/sidecar.rs)), production .app 안에서 그대로 작동하지 않는다.
2. **세션이 누적되지 않는다.** 두 번째 곡을 처리하면 첫 번째 결과는 `output/htdemucs/<title>/`에 그대로 남아있지만, UI에서 이를 다시 열 방법이 없다. 사용자에게 "데스크톱 앱"으로서 가치는 누적된 라이브러리에서 나온다.
3. **assetProtocol scope이 임시값이다.** Phase 2의 `**/output/**`은 webview 보안상 모든 디스크의 `output` 폴더를 열어주는 셈이다 ([phase-2.md:139](./phase-2.md), [tauri.conf.json:24-27](../src-tauri/tauri.conf.json)). Phase 3에서 AppLocalData 단일 base로 좁힌다.
4. **Sidecar 취소 Windows 미구현** ([sidecar.rs:195-199](../src-tauri/src/sidecar.rs)). Phase 4 패키징과 묶는 게 효율적이라 **Phase 3 범위 밖**으로 명시 이관한다 (rationale: Windows 취소는 jobobject 또는 GenerateConsoleCtrlEvent를 써야 하고 .exe 빌드 환경 검증과 한 번에 가는 게 시행착오를 줄인다).

**Phase 3의 목표:** 워크스페이스 루트 의존을 제거하고, 모든 작업물을 `<AppLocalData>/yt-split/` 한 곳으로 모은 뒤, 그 위에 "프로젝트" 엔티티와 라이브러리 UI를 얹는다.

---

## 확정된 결정

이 섹션은 **리뷰 라운드 후 잠긴(locked) 결정**만 적는다. 미해결 항목은 § Open decisions로.

- **베이스 경로:** `tauri::path::PathResolver::app_local_data_dir()` 결과물에 `yt-split/` 하위를 일관 사용. dev/prod 동일 (dev에서도 macOS면 `~/Library/Application Support/com.ytsplit.app/yt-split/`). 워크스페이스 루트의 `./output/`, `./downloads/`는 더 이상 쓰지 않는다.
- **사이드카 인터페이스:** `--workdir <path>` 인자 신설. Rust가 base 경로를 결정해 주입, Python은 `Path.cwd()`에 의존하지 않는다. CLI 사용자가 `--workdir`를 생략하면 기존처럼 `Path.cwd()`로 fallback (회귀 방지).
- **프로젝트 디렉터리 레이아웃:**
    ```
    <base>/
    ├── downloads/                    # yt-dlp raw mp3 (재사용 안 하면 자동 정리는 Phase 4+)
    ├── projects/
    │   ├── <uuid>.json               # 메타데이터
    │   └── <uuid>/
    │       └── stems/
    │           ├── vocals.wav
    │           ├── drums.wav
    │           ├── bass.wav
    │           └── other.wav
    └── logs/                         # 향후 (Phase 5에서 결정)
    ```
    Demucs 기본 출력 트리(`output/htdemucs/<title>/...`)를 더 이상 그대로 노출하지 않는다. 사이드카가 분리 직후 `<base>/projects/<uuid>/stems/`로 **이동(move)**한다.
- **프로젝트 메타데이터 스키마 v1:**
    ```json
    {
      "id": "<uuid v4>",
      "title": "<from yt-dlp info.title>",
      "url": "<original input URL>",
      "created_at": "<ISO 8601 UTC>",
      "device": "cuda|mps|cpu",
      "stem_mode": "all|vocals|drums|bass|other",
      "tracks": { "vocals": "stems/vocals.wav", ... },
      "schema_version": 1
    }
    ```
    `tracks`는 **상대 경로**(`<uuid>/stems/...`에 대한 상대) — base가 바뀌어도 따라온다.
- **assetProtocol scope:** `["$APPLOCALDATA/yt-split/**"]`로 좁힌다. `**/output/**` 제거.
- **사이드카 취소 Windows:** Phase 3 범위 밖. Phase 4와 함께 처리.

---

## 슬라이스

Phase 3은 다음 4개 슬라이스로 쪼갠다. **A → B → C 순서 권장**, D는 생략 가능 (다른 사이트 정리는 Phase 4 패키징과 함께).
현재 리뷰 라운드에서 잠근 실행 범위는 **P3-A + P3-B 우선 확정**이다. P3-C/P3-D는 후속 사이클로 분리한다.

| #        | 슬라이스                                          | 핵심 결과                                                       | 의존   |
| -------- | ------------------------------------------------- | --------------------------------------------------------------- | ------ |
| **P3-A** | AppLocalData base + `--workdir` 인자              | 사이드카가 워크스페이스 루트에 더 이상 쓰지 않는다              | (없음) |
| **P3-B** | 프로젝트 메타데이터 + 디렉터리 재배치             | 분리 결과가 `projects/<uuid>/`로 들어가고 `.json` 메타가 생긴다 | P3-A   |
| **P3-C** | 라이브러리 UI 슬라이스                            | 누적된 프로젝트 리스트 + 클릭 시 Player에 로드                  | P3-B   |
| **P3-D** | (선택) Demucs raw 출력 정리 / 마이그레이션 가이드 | 기존 `./output/` 잔존물 처리                                    | P3-B   |

각 슬라이스는 자체 `/pwrc-plan` 사이클을 다시 받는다. 이 마스터 플랜은 슬라이스 간 인터페이스(NDJSON 이벤트 추가, 메타 스키마, 상대 경로 규약)를 못박는 역할을 한다.

---

## 슬라이스 P3-A — AppLocalData base + `--workdir`

### 변경 파일

| 경로                                                          | 변경                                                                                                                                                                          |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src/app/main.py`](../src/app/main.py)                       | argparse에 `--workdir`. `run_pipeline(base_dir=...)` 인자가 `Path(args.workdir) if args.workdir else Path.cwd()`로 결정. `check_hardware_compatibility(check_path=base_dir)`. |
| [`src/features/system.py`](../src/features/system.py)         | (변경 없음, 이미 `check_path` 인자 받음)                                                                                                                                      |
| [`src-tauri/src/sidecar.rs`](../src-tauri/src/sidecar.rs)     | `tauri::Manager::path()`에서 `app_local_data_dir()` 해석 → `<dir>/yt-split/`을 만들고 `--workdir <dir>` 인자로 사이드카에 전달. `current_dir(workspace_root)` 제거.           |
| [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json)   | `assetProtocol.scope` → `["$APPLOCALDATA/yt-split/**"]`                                                                                                                       |
| [`tests/app/test_pipeline.py`](../tests/app/test_pipeline.py) | `--workdir` 처리 테스트 추가 (아래)                                                                                                                                           |

### 첫 실패 테스트 (P3-A 1차 사이클)

**경로:** `tests/app/test_pipeline.py`
**이름:** `test_main_uses_workdir_arg_for_base_dir`
**기대 동작:** `python -m src.app.main --sidecar --url ... --workdir <tmp>` 로 호출하면 `run_pipeline`의 `base_dir`가 `<tmp>` Path와 같아야 하고, `check_hardware_compatibility`의 `check_path`도 `<tmp>`로 들어가야 한다.

```python
def test_main_uses_workdir_arg_for_base_dir(monkeypatch, tmp_path):
    """--workdir <path> 가 주어지면 run_pipeline.base_dir과
    check_hardware_compatibility.check_path가 모두 그 경로여야 한다."""
    import sys as _sys

    captured = {}

    def fake_check(check_path=None):
        captured["check_path"] = check_path
        return {
            "can_run": True, "warning": "",
            "cuda_available": False, "mps_available": False,
            "demucs_device": "cpu",
            "ram_gb": 16.0, "vram_gb": 0.0, "free_space_gb": 100.0,
        }

    def fake_run(**kwargs):
        captured["base_dir"] = kwargs["base_dir"]
        return True

    monkeypatch.setattr(_sys, "argv", [
        "main.py", "--url", "https://youtu.be/x",
        "--sidecar", "--workdir", str(tmp_path),
    ])
    monkeypatch.setattr("src.app.main.check_hardware_compatibility", fake_check)
    monkeypatch.setattr("src.app.main.ensure_bundled_ffmpeg_on_path", lambda: None)
    monkeypatch.setattr("src.app.main.ensure_shared_ffmpeg_for_torchcodec", lambda: None)
    monkeypatch.setattr("src.app.main.run_pipeline", fake_run)

    from src.app.main import main
    main()

    assert captured["check_path"] == tmp_path
    assert captured["base_dir"] == tmp_path
```

이 테스트는 현재 fail해야 한다(argparse에 `--workdir`가 없어 SystemExit 2).

### Done

- 기존 `tests/app/test_pipeline.py` 4개 모두 통과
- 신규 `test_main_uses_workdir_arg_for_base_dir` 통과
- `cargo check` 통과
- 수동 검증: `pnpm dev` 후 분리 1회. `~/Library/Application Support/com.ytsplit.app/yt-split/downloads/`에 mp3가 떨어지는지 확인.

### 검증 명령

```bash
pytest tests/app/test_pipeline.py -v
(cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" cargo check)
```

---

## 슬라이스 P3-B — 프로젝트 메타데이터 + 디렉터리 재배치

### 변경 파일

| 경로                                                                                                  | 변경                                                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src/features/download.py`](../src/features/download.py)                                             | `extract_info` 결과에서 `info["title"]` 추출 → `download_audio` 반환값을 `tuple[Path, dict]` 또는 별도 dataclass로 확장. NDJSON `stage.done(download)`에 `title` 필드 포함.            |
| [`src/features/separation.py`](../src/features/separation.py)                                         | demucs 호출 후 출력물을 `<base>/projects/<uuid>/stems/`로 이동(또는 처음부터 그곳에 쓰도록 `-o` 인자 조정). 4-stem이면 4개, two-stems면 2개.                                           |
| `src/features/project.py` (신규)                                                                      | `create_project_metadata(base, info, tracks, device, stem_mode) -> Path` — uuid 생성, json write. `list_projects(base) -> list[ProjectMeta]`.                                          |
| [`src/app/main.py`](../src/app/main.py)                                                               | 위 함수를 호출해 메타 파일 작성. NDJSON `stage.done(separate)`에 `project_id`와 절대경로 dict + `project_id`만 동시 포함 (UI는 절대경로로 즉시 재생, 라이브러리는 메타 파일로 재구성). |
| [`ui/src/features/separate-audio/model/events.ts`](../ui/src/features/separate-audio/model/events.ts) | `StageDoneEvent.title?`, `StageDoneEvent.project_id?` 추가.                                                                                                                            |
| `tests/features/test_project.py` (신규)                                                               | 메타 작성/조회 라운드트립 테스트.                                                                                                                                                      |

### 인터페이스 노트

- **프로젝트 ID:** uuid v4 (Python `uuid.uuid4()`). 콘텐츠 해시는 후속 추적이 어렵고, 같은 URL 재다운로드를 구분 못 함.
- **상대 경로 vs 절대 경로:** 메타 파일에는 상대 경로를 저장한다. NDJSON은 `project_id` 중심 계약으로 최소화하고, UI는 `open_project(project_id)` 또는 동일한 resolver를 통해 절대 경로를 복원한다. 같은 정보를 이벤트/메타에 중복 저장하지 않는다.
- **경로 검증 규칙(필수):** 메타에서 읽은 상대 경로는 Rust/Python 양쪽에서 canonicalize 후 `starts_with(<base>/projects/<id>/)`를 만족해야 한다. `..` 포함/탈출 경로는 즉시 에러 처리한다.
- **two-stem 모드:** Demucs `--two-stems vocals` → `vocals.wav` + `no_vocals.wav` 2개. 메타의 `tracks`는 그 2개만, `stem_mode`는 `"vocals"`로 기록.
- **다운로드 캐시:** 같은 URL을 다시 처리하면 새 uuid + 새 mp3. 중복 검출은 Phase 3 범위 밖 (open decision OD-3 참조).
- **출력 경로 전략:** 기본 전략은 `demucs -o <base>/projects/<uuid>/` direct output으로 고정한다. post-move는 예외 복구 루트에서만 사용한다.
- **동시 실행 정책(필수):** Phase 3은 sidecar 단일 실행만 허용한다. 실행 중 추가 요청은 queue 또는 busy 에러로 처리하며, cancel 대상 PID가 교차되지 않도록 보장한다.

### 첫 실패 테스트 (P3-B 1차 사이클)

**경로:** `tests/features/test_project.py`
**이름:** `test_create_project_metadata_writes_v1_schema`

```python
def test_create_project_metadata_writes_v1_schema(tmp_path):
    """메타 파일이 v1 스키마 + 상대 경로로 저장되어야 한다."""
    from src.features.project import create_project_metadata

    tracks = {
        "vocals": tmp_path / "projects" / "abc" / "stems" / "vocals.wav",
        "drums":  tmp_path / "projects" / "abc" / "stems" / "drums.wav",
    }
    for p in tracks.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    meta_path = create_project_metadata(
        base=tmp_path,
        project_id="abc",
        title="Test Song",
        url="https://youtu.be/x",
        device="cpu",
        stem_mode="all",
        tracks=tracks,
    )

    import json
    data = json.loads(meta_path.read_text())
    assert data["schema_version"] == 1
    assert data["id"] == "abc"
    assert data["title"] == "Test Song"
    assert data["device"] == "cpu"
    assert data["tracks"]["vocals"] == "abc/stems/vocals.wav"  # 상대
```

### Done

- v1 스키마 라운드트립 통과
- 분리 1회 후 `<base>/projects/<uuid>.json`과 `<uuid>/stems/*.wav` 4개 존재
- NDJSON `stage.done(separate)`에 `project_id`, `title` 포함
- Player UI는 기존 동작 유지 (회귀 없음)
- 실패 경로 테스트 통과:
    - `--workdir` 미지정 fallback(`Path.cwd()`)
    - workdir 생성/권한 실패 시 명시적 에러
    - 메타 atomic write 실패 시 orphan 감지/복구 경로
    - path traversal(`../`) 입력 차단
    - 동시 실행 시 queue/busy 정책 검증

### 검증 명령

```bash
pytest tests/features/test_project.py tests/app/test_pipeline.py -v
pnpm --dir ui test
```

---

## 슬라이스 P3-C — 라이브러리 UI

### 변경 파일

| 경로                                              | 변경                                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| `ui/src/entities/project/model/types.ts` (신규)   | `ProjectMeta` (events.ts와 별도, 라이브러리 도메인)                      |
| `ui/src/entities/project/api/library.ts` (신규)   | `listProjects()` (Tauri command 호출), `deleteProject(id)`               |
| `ui/src/features/library/ui/Library.tsx` (신규)   | shadcn `Card` 그리드, 클릭 시 Player 로드                                |
| `ui/src/features/library/model/store.ts` (신규)   | Zustand: `items`, `loadingState`, `refresh()`, `deleteAndRefresh()`      |
| [`src-tauri/src/lib.rs`](../src-tauri/src/lib.rs) | 신규 Tauri 명령: `list_projects`, `delete_project`, `open_project`       |
| `src-tauri/src/library.rs` (신규)                 | json 디렉터리 스캔, `serde_json::from_str<ProjectMeta>`                  |
| [`ui/src/app/App.tsx`](../ui/src/app/App.tsx)     | `Library` 패널 추가 (기존 PipelineRunner + Player와 같은 max-w-3xl 컬럼) |

### UX 결정

- **레이아웃:** 단일 컬럼, 위에서 아래로 `[Runner] → [Library] → [Player]`. Sidebar는 미래 작업.
- **클릭 동작:** 메타의 `tracks` 상대 경로를 base와 합쳐 `convertFileSrc`로 변환 → `usePlayerStore.load()`에 직접 주입. Pipeline store는 건드리지 않음.
- **Delete:** 확인 모달 후 2-phase 삭제(삭제 마킹 → 실제 삭제 → 실패 시 복구/재시도 표시). 파일시스템 레벨의 "완전 원자 삭제"를 가정하지 않는다.
- **Refresh:** mount + pipeline `done(ok=true)` 직후 자동 (`useAutoLoadPlayer`와 같은 패턴).
- **빈 상태:** "아직 처리한 곡이 없습니다" + Runner로 스크롤 안내.

### 첫 실패 테스트 (P3-C 1차 사이클)

**경로:** `ui/src/features/library/model/store.test.ts`
**이름:** `library store dedupes refresh and exposes sorted items`

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useLibraryStore } from "./store";

vi.mock("../../entities/project/api/library", () => ({
    listProjects: vi.fn(),
}));

describe("library store", () => {
    beforeEach(() => useLibraryStore.setState({ items: [], status: "idle" }));

    it("loads and sorts items by created_at desc", async () => {
        const { listProjects } =
            await import("../../entities/project/api/library");
        (listProjects as any).mockResolvedValue([
            {
                id: "a",
                title: "Old",
                created_at: "2026-01-01T00:00:00Z",
                url: "",
                device: "cpu",
                stem_mode: "all",
                tracks: {},
                schema_version: 1,
            },
            {
                id: "b",
                title: "New",
                created_at: "2026-05-01T00:00:00Z",
                url: "",
                device: "cpu",
                stem_mode: "all",
                tracks: {},
                schema_version: 1,
            },
        ]);

        await useLibraryStore.getState().refresh();
        const items = useLibraryStore.getState().items;
        expect(items.map((i) => i.id)).toEqual(["b", "a"]);
    });
});
```

### Done

- 라이브러리 store 테스트 통과
- 분리 → Library 자동 갱신 → 항목 클릭 → Player 로드 (수동 검증)
- 기존 vitest 8개 케이스(Phase 2) 회귀 없음

### 검증 명령

```bash
pnpm --dir ui test
pnpm --dir ui build
pnpm dev   # 분리 2회 후 Library에 항목 2개, 첫 항목 클릭 시 Player 재생 확인
```

---

## 슬라이스 P3-D — (선택) 잔존 출력 정리

워크스페이스 루트의 기존 `./output/`, `./downloads/`는 Phase 1·2 산출물. 자동 마이그레이션은 안전성/예측가능성 trade-off가 크다. 권장:

- **선택 1 (default):** 그대로 둔다. README/CHANGELOG에 "Phase 3부터 결과는 AppLocalData로 이동했습니다. 이전 결과는 수동으로 옮기거나 삭제하세요"만 안내.
- **선택 2:** 첫 실행 시 1회 다이얼로그로 "이전 결과를 복사하시겠습니까?" 묻기. 복잡도 높음, Phase 4 마이그레이션 단계에서 묶는 게 자연스러움.

→ **default = 선택 1**. P3-D는 README/CHANGELOG 업데이트만으로 종료.

---

## 결과 (각 슬라이스 완료 시 채움)

- [ ] P3-A 머지: AppLocalData base 동작
- [ ] P3-B 머지: 메타 + 재배치
- [ ] P3-C 머지: Library UI
- [ ] P3-D 머지: 문서화

---

## Open decisions (리뷰 라운드용)

| #        | 항목                                   | 옵션                                                                         | 현재 추천                                                                                                                              | 상태         |
| -------- | -------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| **OD-1** | 다운로드 mp3를 메타에 함께 보존?       | (a) 보존, 메타에 `source_mp3` 경로 (b) 분리 후 삭제                          | **(a)**. 추후 다른 모델로 재분리 가능. 디스크 비용은 Demucs 출력 대비 작음                                                             | **Open**     |
| **OD-2** | 같은 URL 재처리 시 동작                | (a) 항상 새 uuid (b) 기존 프로젝트 덮어쓰기 (c) 사용자에게 묻기              | **(a)**. 단순. 중복 정리는 Phase 4+.                                                                                                   | **Open**     |
| **OD-3** | 메타 v1 → v2 마이그레이션 정책         | (a) `schema_version` 읽고 변환 함수 (b) 무시하고 새 스키마로 강제            | Phase 3에서는 (a) hook만 만들고, 실제 v2까지는 nope.                                                                                   | **Open**     |
| **OD-4** | `delete_project`가 raw mp3까지 지우나? | OD-1과 연동                                                                  | OD-1=(a)면 함께 삭제. 단, 구현은 2-phase delete 기준으로 실패 복구/재시도 상태를 노출한다.                                             | **Open**     |
| **OD-5** | 라이브러리 정렬 기본값                 | created_at desc / title asc / 사용자 toggle                                  | **created_at desc**. toggle은 Phase 5 polish.                                                                                          | **Deferred** |
| **OD-6** | Cancel Windows                         | Phase 3에 포함 vs Phase 4 이관                                               | **Phase 4 이관**. (이미 결정 섹션에 못박음, 다시 검토 시 OD로 복귀.)                                                                   | **Locked**   |
| **OD-7** | `<base>/yt-split/` 중첩이 적절한가?    | (a) `app_local_data_dir() / "yt-split"` (b) `app_local_data_dir()` 직접 사용 | **(a)**. identifier가 이미 `com.ytsplit.app`라 dir 자체는 앱 전용이지만, logs/projects/downloads를 한 우산 아래 두면 정리/백업이 쉬움. | **Open**     |
| **OD-8** | Library 엔티티 위치                    | `ui/src/entities/project/` 단일 vs feature 내부 model                        | **entities 분리**. 다른 feature(예: 추후 export, share)에서 재사용.                                                                    | **Deferred** |

리뷰 시 각 OD에 ✅/✏️ 코멘트 + 선택 이유를 남겨주세요.
상태 정의: **Open**(결정 필요), **Deferred**(후속 슬라이스/Phase로 이관), **Locked**(현재 라운드에서 잠금).

---

## P3-A+B 우선 구현 체크리스트 (완료 시 체크)

아래 체크리스트는 **이번 라운드 범위(P3-A+B)** 에 직접 영향 있는 항목만 모았다.  
구현/테스트가 끝나면 각 항목을 `[x]`로 바꾼다.

### 0) OD 잠금(구현 전)

- [ ] **OD-1 잠금:** mp3 보존 정책 확정(`source_mp3` 포함 여부)
- [ ] **OD-2 잠금:** 동일 URL 재처리 정책 확정(기본: 항상 새 uuid)
- [ ] **OD-3 잠금:** schema_version hook 범위 확정(v1 읽기 + v2 확장 훅만)
- [ ] **OD-4 잠금:** delete 시 raw mp3 삭제 연동 정책 확정(OD-1과 일치)
- [ ] **OD-7 잠금:** `<base>/yt-split/` 중첩 경로 정책 확정

### 1) P3-A 구현

- [ ] `src/app/main.py`에 `--workdir` 인자 추가 및 `Path.cwd()` fallback 유지
- [ ] `check_hardware_compatibility(check_path=base_dir)` 연결 확인
- [ ] `src-tauri/src/sidecar.rs`에서 `app_local_data_dir()/yt-split` 결정 + `--workdir` 주입
- [ ] `current_dir(workspace_root)` 의존 제거
- [ ] `src-tauri/tauri.conf.json` scope를 `["$APPLOCALDATA/yt-split/**"]`로 축소

### 2) P3-B 구현

- [ ] Demucs 출력 전략을 direct output 단일화(`-o <base>/projects/<uuid>/`)
- [ ] `src/features/project.py` 생성(`create_project_metadata`, `list_projects`)
- [ ] 메타 파일 atomic write 적용(`.tmp` → rename)
- [ ] 메타 `tracks`는 상대 경로만 저장
- [ ] 이벤트 계약은 `project_id` 중심으로 최소화(중복 경로 페이로드 축소)
- [ ] 경로 검증 적용(canonicalize + `starts_with(<base>/projects/<id>)`)
- [ ] path traversal(`../`) 즉시 차단

### 3) 동시 실행/삭제 안정성

- [ ] 단일 실행 정책 명시(queue 또는 busy)
- [ ] cancel 대상 PID 교차 방지 로직 반영
- [ ] delete는 2-phase(마킹→삭제→실패 시 복구/재시도 상태 노출)
- [ ] orphan(stems만 있고 json 없음) 탐지 규칙 반영

### 4) 테스트(필수)

- [ ] `test_main_uses_workdir_arg_for_base_dir` 통과
- [ ] `--workdir` 미지정 fallback 테스트 추가/통과
- [ ] workdir 생성/권한 실패 테스트 추가/통과
- [ ] `test_create_project_metadata_writes_v1_schema` 통과
- [ ] 메타 write 실패(orphan) 테스트 추가/통과
- [ ] path traversal 차단 테스트 추가/통과
- [ ] 동시 실행 정책(queue/busy) 테스트 추가/통과

### 5) 검증/문서 동기화

- [ ] `pytest tests/app/test_pipeline.py tests/features/test_project.py -v` 통과
- [ ] `(cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" cargo check)` 통과
- [ ] 수동 검증: AppLocalData 하위에 downloads/projects 생성 확인
- [ ] 이 문서의 `## 결과` 체크박스(P3-A, P3-B) 갱신

---

## Risks

- **AppLocalData 첫 쓰기 권한:** macOS Sandbox가 켜져 있지 않으면 free. 서명/공증(Phase 5)에서 entitlements 추가 시 다시 검토.
- **Demucs 출력 이동 vs in-place 작성:** demucs api는 `-o`로 base를 받지만 안에 자기 마음대로 `htdemucs/<title>/` 트리를 만든다. 이동 단계는 `shutil.move`로 충분하지만, 같은 title 두 번 처리 시 충돌. **uuid 디렉터리에 먼저 분리하도록 `-o <base>/projects/<uuid>/`로 강제**하면 동시 실행도 안전.
- **메타 corruption:** 분리는 끝났는데 메타 write가 실패하면 stems만 남고 라이브러리에서 보이지 않는다. write를 atomic하게 (`<uuid>.json.tmp` → rename) 처리하고, 라이브러리 스캔 시 stems 디렉터리 있는데 메타 없는 케이스를 "orphan"으로 표시.
- **동시 실행 취소 레이스:** 단일 PID 슬롯 구현에서 실행/취소가 교차되면 잘못된 프로세스를 대상으로 cancel될 수 있다. Phase 3에서 단일 실행 정책 + busy/queue 테스트를 필수로 둔다.
- **경로 탈출(path traversal):** 손상된 메타 JSON의 상대 경로(`../`)가 base 밖 파일을 가리킬 수 있다. canonicalize + base prefix 검증 실패 시 즉시 차단한다.
- **assetProtocol scope 좁히기 회귀:** `**/output/**`을 떼는 순간 dev 환경에서 워크스페이스 루트의 기존 결과는 Player에 못 올라간다 (의도된 결과). README에 명시.
- **Migration window:** 사용자가 Phase 2 빌드를 쓰다가 Phase 3 빌드로 업그레이드하면 기존 곡들이 안 보임. 슬라이스 P3-D 문서로 충분한지 리뷰 필요.

---

## Lessons applied

`~/.claude/lessons/Users-kim-young-yin-Documents-codes-yt-split/`: **none yet**. 이번 사이클에서 발생하는 패턴은 `/pwrc-compound`로 첫 lesson 파일을 생성하는 후보가 된다 (예: "메타 + 산출물 분리 시 atomic write가 표준").

---

## Quirks (작업 중 채움)

| 증상                         | 원인 | 해결 |
| ---------------------------- | ---- | ---- |
| _슬라이스 진행하며 채워나감_ |      |      |

---

## 향후 진행

- **Phase 4** — 패키징(`bundle.resources`, sidecar onedir 통째로). Cancel Windows 포함.
- **Phase 5** — CI/배포 + 코드 서명.

이 마스터 플랜이 잠긴 결정으로 마감되면 슬라이스 P3-A부터 `/pwrc-plan`을 다시 호출해 첫 실패 테스트를 잡는다.
