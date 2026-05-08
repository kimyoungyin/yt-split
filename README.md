# yt-split

YouTube URL 하나로 **보컬 · 드럼 · 베이스 · 기타** 4개 트랙을 분리하는 데스크탑 앱.  
Meta의 [Demucs](https://github.com/facebookresearch/demucs) AI 모델(`htdemucs`)을 로컬에서 실행합니다.

English: [below](#english)

---

## 한국어

### 특징

- YouTube URL → 4-stem WAV 분리 (보컬 / 드럼 / 베이스 / 기타)
- 분리된 트랙 멀티트랙 플레이어 (트랙별 볼륨 · 소거 · 솔로)
- 프로젝트 라이브러리 (처리 이력 누적, 언제든 다시 열기)
- 모든 처리가 **내 컴퓨터에서만** 실행됨 — 서버 없음, 클라우드 없음

---

### 패치노트

#### v0.1.0 — 2026-05-09

- YouTube → 4-stem 분리 파이프라인 (yt-dlp + htdemucs)
- 멀티트랙 플레이어 (Web Audio API 기반 샘플 정확 동기)
- 프로젝트 라이브러리 + AppLocalData 저장
- macOS Apple Silicon(arm64) / Intel(x86_64), Windows x86_64, Linux x86_64 패키지

---

### 다운로드

[GitHub Releases](../../releases/latest) 페이지에서 OS에 맞는 파일을 받으세요.

| OS | 파일 |
|----|------|
| macOS Apple Silicon | `yt-split_*_aarch64.dmg` |
| macOS Intel | `yt-split_*_x64.dmg` |
| Windows | `yt-split_*_x64-setup.exe` |
| Linux | `yt-split_*_amd64.AppImage` |

---

### 사용 가이드

#### 설치

**macOS**  
`.dmg`를 열고 앱을 응용 프로그램 폴더로 드래그하세요.  
> 코드 서명 없이 배포된 경우 Gatekeeper가 "개발자를 확인할 수 없습니다" 경고를 표시합니다.  
> 이 경우: Finder에서 앱을 **우클릭 → 열기**를 선택하고 팝업에서 다시 "열기"를 클릭하세요. 이후엔 정상적으로 실행됩니다.

**Windows**  
`.exe` 설치 프로그램을 실행하세요. SmartScreen 경고가 뜨면 "추가 정보 → 실행"을 클릭하세요.

**Linux**  
`.AppImage` 파일에 실행 권한을 부여한 후 실행하세요.
```bash
chmod +x yt-split_*.AppImage
./yt-split_*.AppImage
```

#### 첫 실행 — 모델 다운로드

첫 번째 분리 시 Demucs 모델 가중치를 자동으로 내려받습니다.

- **용량:** 약 2GB
- **저장 위치:** `~/.cache/torch/hub/` (운영체제 기본 캐시)
- **소요 시간:** 인터넷 속도에 따라 5~20분
- 이후 실행부터는 즉시 시작합니다.

안정적인 인터넷 연결 상태에서 첫 실행을 권장합니다.

#### 분리하기

1. 앱 상단 URL 입력창에 YouTube URL을 붙여넣습니다.
2. **분리 시작** 버튼을 클릭합니다.
3. 진행 상황이 단계별로 표시됩니다.
   - 오디오 다운로드 → AI 분리 → 완료
4. 완료 후 멀티트랙 플레이어가 열립니다.

#### 플레이어

| 기능 | 설명 |
|------|------|
| 볼륨 슬라이더 | 트랙별 음량 조절 |
| 소거(Mute) | 해당 트랙 음소거 |
| 솔로(Solo) | 해당 트랙만 재생 |

#### 라이브러리

이전에 처리한 모든 프로젝트가 왼쪽 라이브러리 패널에 쌓입니다. 항목을 클릭하면 즉시 플레이어로 열립니다.

#### 결과물 저장 위치

| OS | 경로 |
|----|------|
| macOS | `~/Library/Application Support/com.ytsplit.app/yt-split/` |
| Windows | `%APPDATA%\com.ytsplit.app\yt-split\` |
| Linux | `~/.local/share/com.ytsplit.app/yt-split/` |

하위 구조:
```
yt-split/
├── downloads/        # yt-dlp 원본 mp3
└── projects/
    ├── <uuid>.json   # 프로젝트 메타 (제목·URL·날짜·스템 모드)
    └── <uuid>/
        └── stems/
            ├── vocals.wav
            ├── drums.wav
            ├── bass.wav
            └── other.wav
```

---

### 자주 묻는 질문

**Q. 인터넷 연결이 계속 필요한가요?**  
모델 가중치를 처음 내려받을 때만 필요합니다. 이후 분리 작업은 완전히 오프라인으로 실행됩니다. YouTube URL 다운로드는 당연히 인터넷이 필요합니다.

**Q. 처리 시간이 얼마나 걸리나요?**  
4분짜리 곡 기준으로 Apple Silicon Mac에서 약 1~3분, CPU만 있는 환경에서 5~15분입니다. NVIDIA GPU가 있으면 1분 이내입니다.

**Q. 지원되지 않는 YouTube URL이 있나요?**  
저작권 보호로 다운로드가 막힌 영상, 연령 제한 영상, 비공개 영상은 처리할 수 없습니다.

---

## English

### What it does

yt-split is a desktop app that downloads audio from a YouTube URL and separates it into four stems — **Vocals · Drums · Bass · Other** — using Meta's [Demucs](https://github.com/facebookresearch/demucs) AI model (`htdemucs`). Everything runs locally on your machine.

---

### Changelog

#### v0.1.0 — 2026-05-09

- YouTube → 4-stem separation pipeline (yt-dlp + htdemucs)
- Multi-track player (sample-accurate sync via Web Audio API, per-track volume / mute / solo)
- Project library + persistent AppLocalData storage
- Packages for macOS Apple Silicon & Intel, Windows x86_64, Linux x86_64

---

### Download

Get the installer for your OS from the [Releases](../../releases/latest) page.

| OS | File |
|----|------|
| macOS Apple Silicon | `yt-split_*_aarch64.dmg` |
| macOS Intel | `yt-split_*_x64.dmg` |
| Windows | `yt-split_*_x64-setup.exe` |
| Linux | `yt-split_*_amd64.AppImage` |

---

### Usage guide

#### Installation

**macOS**  
Open the `.dmg` and drag the app to Applications.  
> If the app is unsigned, Gatekeeper will say "developer cannot be verified."  
> To open anyway: **right-click the app → Open** in Finder, then click "Open" in the dialog. The app will open normally after that.

**Windows**  
Run the `.exe` installer. If SmartScreen warns you, click "More info → Run anyway."

**Linux**  
Make the AppImage executable, then run it.
```bash
chmod +x yt-split_*.AppImage
./yt-split_*.AppImage
```

#### First launch — model download

On the first separation, the app downloads Demucs model weights automatically.

- **Size:** ~2 GB
- **Location:** `~/.cache/torch/hub/` (OS default cache)
- **Time:** 5–20 minutes depending on your connection
- Subsequent runs start immediately.

Run the first separation on a stable internet connection.

#### Separating a track

1. Paste a YouTube URL into the input field at the top.
2. Click **Start**.
3. Watch the progress: download → AI separation → done.
4. The multi-track player opens automatically when finished.

#### Player controls

| Control | Description |
|---------|-------------|
| Volume slider | Adjust per-track level |
| Mute | Silence that track |
| Solo | Play only that track |

#### Library

Every processed project appears in the left Library panel. Click any entry to reopen it instantly in the player.

#### Where files are saved

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/com.ytsplit.app/yt-split/` |
| Windows | `%APPDATA%\com.ytsplit.app\yt-split\` |
| Linux | `~/.local/share/com.ytsplit.app/yt-split/` |

```
yt-split/
├── downloads/        # raw yt-dlp mp3
└── projects/
    ├── <uuid>.json   # metadata (title, URL, date, stem mode)
    └── <uuid>/
        └── stems/
            ├── vocals.wav
            ├── drums.wav
            ├── bass.wav
            └── other.wav
```

---

### FAQ

**Q. Do I need an internet connection to separate tracks?**  
Only for the initial model download and to fetch the YouTube audio. The AI separation itself runs entirely offline after that.

**Q. How long does separation take?**  
A 4-minute song takes roughly 1–3 minutes on Apple Silicon, 5–15 minutes on CPU-only machines, and under 1 minute with an NVIDIA GPU.

**Q. Some YouTube URLs don't work — why?**  
Copyright-blocked videos, age-restricted videos, and private videos cannot be downloaded by yt-dlp.

---

## 개발자 가이드 / Developer Guide

### 아키텍처 / Architecture

```
UI (Vite + React + Zustand)  ─── Tauri IPC ───  Rust (Tauri v2, tokio)
                                                        │
                                              tokio::process::Command
                                                        │
                                          Python sidecar (PyInstaller bundle)
                                          yt-split-py-<triple>/yt-split-py
                                                        │
                                              NDJSON events → stdout
                                              stderr → log channel
```

**이벤트 프로토콜 / Event protocol (NDJSON, one line per event):**

```jsonc
{"type":"hardware", ...}                        // 시작 시 1회
{"type":"stage", "status":"start"|"done", ...}  // 단계 시작/완료
{"type":"progress","stage":..., "value":0..1}   // 진행률
{"type":"error", "stage":..., "message":...}    // 오류
{"type":"done", "ok":true|false}                // 최종
```

### 기술 스택 / Tech stack

| 레이어 | 기술 |
|--------|------|
| UI | React 18, Vite, Zustand, shadcn/ui, Tailwind CSS |
| 데스크탑 shell | Tauri v2 (Rust, tokio) |
| AI 파이프라인 | Python 3.11, Demucs (htdemucs), yt-dlp, torchcodec |
| 패키징 | PyInstaller (onedir), Tauri bundler |
| CI | GitHub Actions (macos-14, macos-13, ubuntu-22.04, windows-latest) |

### 로컬 개발 환경 / Local development

**필요 사항 / Prerequisites**

- Python 3.10+
- Rust (stable)
- Node 20 + pnpm 9
- FFmpeg (시스템 설치 / system install)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
  - Windows: `choco install ffmpeg`

**설정 및 실행 / Setup and run**

```bash
# 1. Python 의존성 + PyInstaller 사이드카 빌드 (5~10분)
pip install -r requirements.txt
bash pyinstaller/build.sh          # Windows: pwsh pyinstaller/build.ps1

# 2. UI 의존성
pnpm --dir ui install

# 3. 개발 서버 (Vite + cargo run + Tauri 윈도우)
pnpm dev

# 4. 프로덕션 앱 빌드
pnpm build:app
```

> `pnpm build:app`은 항상 `bash pyinstaller/build.sh` **이후에** 실행해야 합니다.  
> `build.sh`가 `src-tauri/binaries/<triple>/`에 사이드카를 스테이징하고  
> `tauri.conf.json`의 `bundle.resources`를 현재 플랫폼 triple로 자동 패치합니다.

### 테스트 / Tests

```bash
# Python
pytest

# UI (Vitest)
pnpm --dir ui test

# Rust
cd src-tauri && cargo test
```

### 주요 디렉터리 / Key directories

```
.
├── src/                          # Python 파이프라인 (FSD 구조)
│   ├── app/main.py               # CLI 진입점 (--url, --check, --sidecar)
│   └── features/
│       ├── download/             # yt-dlp 오디오 추출
│       ├── separation/           # Demucs 추론
│       ├── ffmpeg_env.py         # 공유 라이브러리 경로 설정
│       └── progress.py           # NDJSON 이벤트 이미터
├── src-tauri/src/
│   ├── lib.rs                    # Tauri 앱 진입점
│   └── sidecar.rs                # 사이드카 spawn · 이벤트 라우팅 · 취소
├── ui/src/features/
│   ├── separate-audio/           # 분리 파이프라인 UI slice
│   ├── audio-player/             # 멀티트랙 플레이어 slice
│   └── library/                  # 프로젝트 라이브러리 slice
├── pyinstaller/
│   ├── yt-split-py.spec          # PyInstaller 번들 스펙
│   ├── build.sh                  # macOS/Linux 사이드카 빌드 + 스테이징
│   └── build.ps1                 # Windows 사이드카 빌드 + 스테이징
├── .github/workflows/
│   └── build.yml                 # CI: 4-OS matrix 빌드 + artifact upload
└── docs/
    ├── roadmap.md
    ├── phase-4.md                # 프로덕션 패키징 계획 및 결과
    └── phase-5.md                # CI/배포 + 코드 서명 계획
```
