# Tauri + React 마이그레이션 — Phase 1

## Context

기존 yt-split는 `python -m src.app.main --url ...`로 동작하는 CLI 파이프라인이다 (yt-dlp → Demucs `htdemucs`). 사용자는 이를 Tauri v2 + React(Vite) 데스크톱 앱으로 옮기려 한다. 최종 비전은 **멀티트랙 플레이어 + 프로젝트 라이브러리 + GitHub Actions 배포**이지만, 이 플랜은 **Phase 1**만 다룬다.

**Phase 1의 목표:** UI/플레이어/라이브러리 작업 전에 가장 리스크가 큰 부분을 먼저 검증한다 — Python 사이드카 계약(JSON line stdout), PyInstaller 풀번들(PyTorch 포함, ~1.5–2.5GB), Tauri v2 Rust ↔ Python 사이드카 브릿지. macOS 로컬에서 한 번의 사이드카 실행이 React 화면에 진행률을 흘려주는 시점까지를 완료선으로 본다.

**확정된 결정:**
- Demucs는 in-process 호출로 마이그레이션 (subprocess 제거).
- PyInstaller에 PyTorch 풀번들. 첫 실행 시 모델 가중치(`htdemucs` ~80MB)는 PyTorch hub 기본 위치에서 다운로드.
- 기존 CLI 모드(`--url`)는 보존. 사이드카 모드는 `--sidecar` 플래그로 활성화하는 별도 출력 채널이다.

---

## 디렉터리 구조

기존 `src/`는 그대로 두고 루트에 Tauri/프런트 디렉터리를 추가한다.

```
yt-split/
├── src/                          # Python CLI / sidecar
│   ├── app/main.py               # --sidecar 플래그 분기
│   └── features/
│       ├── separation.py         # demucs.separate.main + tqdm hijack
│       ├── progress.py           # NDJSON emitter (sys.__stdout__)
│       ├── download.py           # yt-dlp + progress_hooks
│       ├── system.py
│       └── ffmpeg_env.py
├── pyinstaller/
│   ├── yt-split-py.spec
│   └── build.sh                  # target-triple suffix staging
├── src-tauri/                    # Tauri v2
│   ├── Cargo.toml                # tokio process/io-util (no shell plugin)
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs                # invoke_handler!(run_pipeline)
│   │   └── sidecar.rs            # tokio spawn + NDJSON line → emit
│   └── binaries/<triple>/        # PyInstaller 산출물 (gitignored)
├── ui/                           # Vite + React + TS, FSD 구조
│   └── src/
│       ├── app/                  # entry, providers
│       ├── features/separate-audio/{api,model,ui}/
│       └── main.tsx
├── package.json                  # 루트, tauri 스크립트
└── pytest.ini                    # testpaths=tests/
```

`tauri.conf.json`의 `build.frontendDist`는 `../ui/dist`, `build.devUrl`은 `http://localhost:5173`로 지정한다.

---

## 작업 순서

### 1. Python 사이드카 계약 + Demucs in-process 호출

수정 대상:
- `src/app/main.py`: `--sidecar` 플래그 추가. 활성화 시 모든 사용자 메시지(print, warning, error)는 **NDJSON**으로 stdout에 출력. argparse는 그대로.
- `src/features/separation.py`: 기존 `subprocess.run([sys.executable, "-m", "demucs.separate", ...])`을 제거하고 `demucs.separate.main(opts)`을 in-process로 호출. `demucs.apply.tqdm`을 monkey-patch한 wrapper로 segment 진행률을 추출.
- `src/features/progress.py` (신규): `emit(type, **fields)` → `json.dumps({"type": type, **fields}) + "\n"`을 sys.__stdout__에 한 줄씩 flush. sidecar 모드일 때만 동작.
- `src/features/download.py`: yt-dlp `progress_hooks`로 다운로드 % → `emit("progress", stage="download", value=...)`. sidecar 모드에선 `noprogress=True`, `logtostderr=True`도 같이 켜서 사람용 progress bar가 stdout으로 새지 않게.

**JSON 라인 프로토콜 (NDJSON, 한 줄 = 한 이벤트):**
```
{"type":"hardware","cuda_available":false,"mps_available":true,"demucs_device":"mps","ram_gb":24.0,"vram_gb":0.0,"free_space_gb":136.2,"can_run":true,"warning":""}
{"type":"stage","stage":"download","status":"start","url":"..."}
{"type":"progress","stage":"download","value":0.42}
{"type":"stage","stage":"download","status":"done","path":"/.../song.mp3"}
{"type":"stage","stage":"separate","status":"start","model":"htdemucs","device":"mps"}
{"type":"progress","stage":"separate","value":0.18}
{"type":"stage","stage":"separate","status":"done","tracks":{"vocals":"...","drums":"...","bass":"...","other":"..."}}
{"type":"done","ok":true}
{"type":"error","stage":"separate","message":"..."}
```

매 emit마다 `flush()`. exit code는 성공 0, 실패 1.

### 2. PyInstaller spec + 로컬 빌드

- `pyinstaller/yt-split-py.spec` (`--onedir`):
  - `collect_submodules`: `demucs`, `yt_dlp`, `torchaudio`, `torchcodec`, `numpy`
  - `collect_data_files`: `demucs/remote/*.yaml`, `torchcodec/*`
  - `collect_dynamic_libs("torchcodec")` — `libtorchcodec_core{4..8}.dylib` 등 staging
  - macOS Homebrew/Linux 시스템 FFmpeg shared libs(`libav*`, `libsw*`, `libpost*`)를 `binaries`에 직접 추가
- `pyinstaller/build.sh`: target-triple suffix(`yt-split-py-aarch64-apple-darwin/`)로 rename + `src-tauri/binaries/`로 staging.

### 3. Tauri v2 셸 + Rust 사이드카 브릿지

- `src-tauri/`를 수동 생성 (`npm create tauri-app` 사용 안 함, 기존 폴더 보존).
- 의존성: `tauri = "2"`, `tokio = "1"` features `["sync", "process", "io-util", "rt-multi-thread", "macros"]`. `tauri-plugin-shell`은 사용하지 않는다 — onedir 사이드카는 단일 binary가 아니라 폴더 전체가 필요해 `externalBin` 자동 staging과 호환되지 않으므로 직접 `tokio::process::Command`로 spawn한다.
- `src-tauri/src/sidecar.rs`:
  - target triple 자동 감지로 `binaries/yt-split-py-<triple>/yt-split-py` 절대 경로 해석
  - `current_dir`을 `CARGO_MANIFEST_DIR`의 부모(워크스페이스 루트)로 고정 → 사이드카가 `downloads/`, `output/`을 프로젝트 루트에 생성
  - stdout `BufReader::lines()`를 `serde_json`으로 파싱 → `app.emit("yt-split:event", value)`
  - stderr는 `yt-split:log`로, 종료 코드는 `yt-split:done`으로 emit
- `#[tauri::command] async fn run_pipeline(args: PipelineArgs)` 하나만 노출.

### 4. React (Vite) FSD 셸 + 진행률 수신

- `ui/`를 Vite + React + TS로 초기화. Tailwind/shadcn/Lucide는 후속 Phase.
- Zustand 스토어 `ui/src/features/separate-audio/model/store.ts`: `{status, currentStage, progress, hardware, tracks, errorMessage, logs}`.
- `ui/src/features/separate-audio/api/sidecar.ts`:
  - `invoke("run_pipeline", { args: { url, stem } })`
  - `attachSidecarListeners()`는 idempotent. **`globalThis.__ytSplitSidecarAttach`에 promise 캐시**해서 React StrictMode의 double-invoke + Vite HMR 모듈 재평가에도 listener 1회만 등록.
- `ui/src/app/App.tsx`: URL input + Run 버튼 + 단계별 진행률 + 트랙 리스트. cleanup 함수는 두지 않음 (사이드카 채널은 webview lifetime).

### 5. 통합 검증

- `pnpm dev` 후:
  1. URL 입력 → Run 클릭
  2. `hardware → download (0~100%) → separate (0~100%) → done` 흐름
  3. 출력 디렉터리에 `vocals/drums/bass/other.wav` 4개
- `pytest`, `cargo build` 모두 통과
- `pnpm build:app`은 prod 패키징(후속 Phase) 검증용

---

## Phase 1 비포함 (후속 Phase 후보)

- 멀티트랙 플레이어 (Web Audio API), 마스터 재생/볼륨, 솔로/뮤트
- 프로젝트 라이브러리(AppData 스캔), 메타데이터 저장
- shadcn/ui, Lucide React 도입 및 디자인
- Windows/Linux PyInstaller spec, FFmpeg DLL 수집
- GitHub Actions matrix 빌드, 코드 서명/공증
- 사이드카 취소(SIGTERM) 기능
- 프로덕션 패키징: onedir 폴더를 `bundle.resources`로 복사하고 prod path resolution 추가

---

## Phase 1 결과 — 실제 구현 노트

### 검증된 워크플로우 (macOS arm64, MPS)

```bash
# 사이드카 단독
python -m src.app.main --check --sidecar          # → hardware 1줄
python -m src.app.main --url <URL> --sidecar      # → 풀 NDJSON 스트림

# PyInstaller 빌드 (5–10분, 약 411MB onedir)
bash pyinstaller/build.sh

# 번들 단독 (clean shell)
env -i HOME="$HOME" PATH="/usr/bin:/bin" \
  ./src-tauri/binaries/yt-split-py-aarch64-apple-darwin/yt-split-py --check --sidecar

# Tauri 통합
pnpm --dir ui install
pnpm dev                                          # vite + cargo run + 윈도우 spawn
```

`pytest`로 24개 테스트 모두 통과.

### 처음 의도와 달라진 부분

- **Demucs API**: 처음엔 `demucs.api.Separator` + `apply_model(callback=)`을 쓰려 했으나, demucs 4.0.1엔 `demucs.api`가 없고 `apply_model`도 callback 인자가 없다. 대신 `demucs.separate.main(opts)`을 in-process 호출하면서 `demucs.apply.tqdm`을 monkey-patch한 iterable wrapper로 segment 진행률을 빼낸다 (`src/features/separation.py:_ProgressTqdm`). htdemucs는 BagOfModels(1)이라 진행률 1회 0→1.0.
- **사이드카 spawn 방식**: 처음엔 `tauri-plugin-shell`의 `externalBin` + sidecar API를 쓰려 했으나, PyInstaller `--onedir`은 단일 binary가 아니라 폴더 전체(`yt-split-py/_internal/...`)가 필요해 호환되지 않는다. plugin-shell 의존성을 제거하고 `tokio::process::Command`로 직접 spawn (`src-tauri/src/sidecar.rs`). 프로덕션 패키징은 후속 Phase에서 폴더를 `bundle.resources`로 staging.
- **emitter는 `sys.__stdout__`**: demucs/yt-dlp의 사람용 print를 stderr로 redirect하기 위해 `contextlib.redirect_stdout(sys.stderr)` 컨텍스트를 쓰는데, emitter가 `sys.stdout`을 쓰면 emit도 같이 stderr로 새 NDJSON 채널이 끊긴다. emitter는 `sys.__stdout__`(파이썬 시작 시점의 진짜 stdout)에 직접 쓰도록 했다.
- **사이드카 cwd**: Tauri dev는 cwd를 `src-tauri/`로 잡고 자식 프로세스를 spawn한다. 사이드카가 `Path.cwd()`로 출력 경로를 만들면 `src-tauri/output/`에 파일이 생긴다. Rust에서 `current_dir(<workspace_root>)`으로 명시적으로 고정.

### 발견된 quirks와 해결 (커밋 8a7368d, eb70a59)

| 증상 | 원인 | 해결 |
|---|---|---|
| stdout NDJSON 사이에 yt-dlp progress bar 라인 | `quiet=True`만으론 `[download] N%` 차단 안 됨 | `noprogress=True`, `logtostderr=True` 동시 |
| `No module named 'numpy.core.multiarray'` | numpy 2.x의 `numpy.core` lazy alias가 PyInstaller 정적 분석에서 누락 | spec에 `collect_submodules("numpy")` |
| `Could not load libtorchcodec` | 번들에 torchcodec 폴더 자체가 없음 + 시스템 FFmpeg shared libs 누락 | `collect_dynamic_libs("torchcodec")` + Homebrew `libav*.dylib` 직접 binaries 추가 |
| GUI logs에 같은 stderr 라인이 2번씩 | React StrictMode + Vite HMR이 listener 등록을 중복시킴 | `globalThis.__ytSplitSidecarAttach`에 promise 캐시, `useEffect` cleanup 제거. (Tauri Discussion #5194 패턴) |
| `pytest`가 PyInstaller 산출물 안의 torch 테스트를 collect 시도 | testpaths 미지정 | `pytest.ini`에 `testpaths = tests` |
| `tauri dev` 첫 시도 실패: `'/Users/.../codes/ui'` 없음 | `beforeDevCommand`의 cwd가 프로젝트 루트라 `../ui`가 아니라 `ui`가 맞음 | `tauri.conf.json` 수정 |

### 핵심 파일 빠른 참조

| 영역 | 파일 |
|---|---|
| 사이드카 진입 | `src/app/main.py` |
| NDJSON emitter | `src/features/progress.py` |
| Demucs in-process | `src/features/separation.py` |
| 다운로드 hook | `src/features/download.py` |
| 하드웨어 체크 | `src/features/system.py` |
| FFmpeg lib path | `src/features/ffmpeg_env.py` |
| PyInstaller spec | `pyinstaller/yt-split-py.spec` |
| Tauri 진입/브릿지 | `src-tauri/src/{lib.rs,sidecar.rs}` |
| Tauri 설정 | `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json` |
| 사이드카 이벤트 타입 | `ui/src/features/separate-audio/model/events.ts` |
| Zustand 스토어 | `ui/src/features/separate-audio/model/store.ts` |
| listen + invoke | `ui/src/features/separate-audio/api/sidecar.ts` |
| UI 위젯 | `ui/src/features/separate-audio/ui/PipelineRunner.tsx` |

### Phase 1 관련 커밋

```
3bfdf01 chore: 루트 package.json + pytest 설정 + 권한 캐시
eb70a59 fix(tauri): 사이드카 cwd 고정 + listener 중복 등록 방지
8a7368d fix(sidecar): NDJSON 채널 오염 차단 + numpy/torchcodec 번들
8a51d1d feat: React (Vite) FSD 셸 + 진행률 수신
86b3c8f feat: Tauri v2 셸 + Rust 사이드카 브릿지
0730f23 feat: PyInstaller spec + 로컬 빌드 검증
b3d5885 feat: python sidecar 설정 + demucs api 전환
```
