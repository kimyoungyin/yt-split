# yt-split

YouTube URL에서 **yt-dlp**로 오디오를 내려받고, **Demucs**(`htdemucs`)로 스템을 분리하는 로컬 파이프라인입니다. 프로젝트 규칙·하드웨어 점검은 [CLAUDE.md](./CLAUDE.md)를 참고하세요.  
English: [below](#english).

## 한국어

### 요약: 필요한 것

- **Python 3.10+** (Windows는 venv를 만들기 전에 `python` / `py`가 `PATH`에 있는지 확인. [python.org](https://www.python.org/) 등에서 설치.)
- **Python 패키지**: `pip install -r requirements.txt` (아래 **처음 설치 (Git 클론)** 절차 참고).
- **FFmpeg**
    - **static-ffmpeg**(`requirements.txt`에 포함): 시스템에 `ffmpeg`가 없을 때 `PATH`에 `ffmpeg` / `ffprobe`를 쓸 수 있게 합니다. **첫 `--url` 실행** 시 바이너리를 **내려받을 수 있으며**(네트워크 필요) 이미 `PATH`에 `ffmpeg`가 있으면 그쪽을 씁니다.
    - **스템 저장(Demucs)**: PyTorch / `torchaudio`가 **torchcodec**을 쓰므로, FFmpeg **공유 라이브러리**(예: `libavutil`)가 필요합니다. static 번들로는 **대체할 수 없습니다**. **첫** `python -m src.app.main --url ...` **이전에** 아래 OS별로 시스템 FFmpeg를 설치하세요.
- **첫 전체 실행**: Demucs가 **모델 가중치**를 내려받을 수 있으며(대략 **~2GB** 수준, PyTorch 캐시), **디스크 여유**가 있어야 합니다(앱이 현재 작업 디렉터리 기준으로도 일정 이상의 여유를 요구합니다. [CLAUDE.md](./CLAUDE.md)). 첫 `--url`은 시간이 걸릴 수 있으니 **네트워크**를 안정적으로 두세요.

### 처음 설치 (Git 클론)

터미널에서 **아래 순서**대로 진행하세요.

#### 1. 저장소 클론

```bash
git clone <REPO_URL> yt-split
cd yt-split
```

`<REPO_URL>`은 GitHub의 이 프로젝트 HTTPS 또는 SSH URL로 바꿉니다.

#### 2. 시스템 FFmpeg(공유 라이브러리) 설치 — **첫 `--url` 이전에**

`pip install`과 **별도**이며, **torchcodec**용입니다.

| OS                           | 명령 / 비고                                                                                                                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **macOS** (Homebrew)         | `brew install ffmpeg` — 라이브러리 경로 예: Apple Silicon `/opt/homebrew/opt/ffmpeg/lib`, Intel Homebrew `/usr/local/opt/ffmpeg/lib`. 해당 `lib`가 있으면 CLI가 `DYLD_LIBRARY_PATH` 앞에 붙입니다.            |
| **Linux** (Debian/Ubuntu 등) | 예: `sudo apt update && sudo apt install -y ffmpeg` — `libavutil`이 일반적인 경로(예: `/usr/lib/x86_64-linux-gnu`)에 있어야 합니다.                                                                           |
| **Windows**                  | **공유 DLL**이 포함된 FFmpeg 빌드를 쓰고, [torchcodec Windows 안내](https://github.com/pytorch/torchcodec#installing-torchcodec)에 맞게 설정하세요. 이 앱이 해당 DLL용 `PATH`를 자동으로 잡아주지는 않습니다. |

#### 3. 가상환경 생성 및 Python 의존성 설치

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows (cmd): .venv\Scripts\activate.bat
                             # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

CLI는 **저장소 루트**(`yt-split/`)에서 실행해 `import src`가 동작하도록 하세요.

#### 4. 하드웨어 확인 후 전체 파이프라인 실행

```bash
python -m src.app.main --check
python -m src.app.main --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

선택: 스템 하나만 — `python -m src.app.main --url "https://..." --stem vocals` (`drums` / `bass` / `other` 동일).

**출력**은 **명령을 실행한 현재 작업 디렉터리** 기준 `./downloads`, `./output`에 생깁니다(`src/` 안이 아님).

#### `--check`와 `--url`의 차이

- **`--check`**: CUDA, MPS, RAM, Demucs 장치, 경고를 출력합니다. 실제 `--url`과 **동일한** FFmpeg / torchcodec 준비를 돌리지 **않고**, 오디오를 받지도 **않습니다**. `--check`는 통과했는데 `--url`에서 FFmpeg·코덱 오류가 나면 **2번 단계**와 [torchcodec 설치](https://github.com/pytorch/torchcodec#installing-torchcodec)를 다시 확인하세요.
- **`--url`**: 번들 경로의 FFmpeg(필요 시 `static-ffmpeg`)와 torchcodec용 공유 lib 경로를 적용한 뒤, 다운로드·분리를 수행합니다. 의존성을 갖춘 **끝에서 끝** 검증은 이걸 쓰세요.

### 설치 앱 / 배포용 바이너리로 받는 경우

이 저장소는 **Git 클론 + venv + `requirements.txt` + 위의 시스템 FFmpeg** 기준으로 설명합니다. **독립 앱**(설치 프로그램, zip, 포터블 등)을 배포하는 경우, **Python 런타임·venv(또는 내장 deps)·FFmpeg+공유 라·모델 캐시** 위치는 직접 문서화하거나 스크립트로 묶어야 하며, **이 저장소에서 자동화하지 않습니다**.

### CLI 옵션

| 플래그      | 설명                                     |
| ----------- | ---------------------------------------- |
| `--check`   | CUDA, RAM, 경고 등 출력(다운로드 없음)   |
| `--url URL` | 처리할 YouTube URL                       |
| `--stem`    | 선택: `vocals`, `drums`, `bass`, `other` |

### 데스크탑 앱 (Tauri)

`pnpm dev` 또는 빌드된 `.app`으로 실행합니다. CLI와 달리 **모든 결과물은 OS 앱 데이터 디렉터리**에 저장됩니다.

| OS | 경로 |
| --- | --- |
| macOS | `~/Library/Application Support/com.ytsplit.app/yt-split/` |
| Windows | `%APPDATA%\com.ytsplit.app\yt-split\` |
| Linux | `~/.local/share/com.ytsplit.app/yt-split/` |

하위 구조:

```
yt-split/
├── downloads/          # yt-dlp 원본 mp3
└── projects/
    ├── <uuid>.json     # 프로젝트 메타데이터 (제목·URL·기기·스템 모드)
    └── <uuid>/
        └── stems/      # 분리된 wav 파일
```

**Phase 1·2 빌드에서 업그레이드하는 경우:** 이전 결과는 저장소 루트의 `./output/`에 남아있으며 라이브러리에 자동으로 나타나지 않습니다. 수동으로 옮기거나 URL을 다시 처리하세요.

### 테스트

```bash
pytest
```

---

## English

[↑ Korean](#한국어)

Local pipeline: download audio from a YouTube URL with **yt-dlp**, separate stems with **Demucs** (`htdemucs`). See [CLAUDE.md](./CLAUDE.md) for project rules and hardware checks.

### Requirements (summary)

- **Python 3.10+** (install from [python.org](https://www.python.org/) or your OS package manager; on Windows, ensure `python` / `py` is on your `PATH` before creating a venv).
- **Python dependencies**: `pip install -r requirements.txt` (see **First-time setup (Git clone)** below in this section).
- **FFmpeg**:
    - **static-ffmpeg** (from `requirements.txt`) can supply `ffmpeg` / `ffprobe` on your `PATH` when missing. The first `--url` run may **download** those binaries (**network** required). If `ffmpeg` is already on your `PATH`, that copy is used instead.
    - **Stem writing (Demucs)**: PyTorch / `torchaudio` uses **torchcodec**, which needs FFmpeg **with shared libraries** (e.g. `libavutil`). The static bundle **does not** replace those shared libs. Install system FFmpeg as below **before the first** `python -m src.app.main --url ...`.
- **First full run**: Demucs may **download model weights** (on the order of **~2GB** into PyTorch’s cache) and needs **enough free disk** (the app also expects sufficient space under the current working directory; see [CLAUDE.md](./CLAUDE.md)). Allow time and a stable network on first `--url`.

### First-time setup (Git clone)

Do these **in order** from a terminal.

#### 1. Clone the repository

```bash
git clone <REPO_URL> yt-split
cd yt-split
```

Use the HTTPS or SSH URL of this project on GitHub (replace `<REPO_URL>`).

#### 2. Install system FFmpeg (shared libraries) — before the first `--url`

Pick your OS. This is **in addition to** `pip install`; it satisfies **torchcodec**, not `pip` alone.

| OS                              | Command / notes                                                                                                                                                                                                                                             |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **macOS** (Homebrew)            | `brew install ffmpeg` — typical library paths: Apple Silicon `/opt/homebrew/opt/ffmpeg/lib`, Intel Homebrew `/usr/local/opt/ffmpeg/lib`. The CLI prepends that `lib` directory to `DYLD_LIBRARY_PATH` when it exists.                                       |
| **Linux** (Debian/Ubuntu, etc.) | e.g. `sudo apt update && sudo apt install -y ffmpeg` so `libavutil` is available under usual paths (e.g. `/usr/lib/x86_64-linux-gnu`).                                                                                                                      |
| **Windows**                     | Use an FFmpeg build that includes **shared DLLs** and matches [torchcodec’s Windows guidance](https://github.com/pytorch/torchcodec#installing-torchcodec). The app does not auto-configure `PATH` for those DLLs; you set it as torchcodec’s docs require. |

#### 3. Create a virtual environment and install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows (cmd): .venv\Scripts\activate.bat
                             # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Run all CLI commands from the **repository root** (`yt-split/`) so `import src` works.

#### 4. Check hardware, then run the full pipeline

```bash
python -m src.app.main --check
python -m src.app.main --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Optional: limit to one stem pair — `python -m src.app.main --url "https://..." --stem vocals` (or `drums` / `bass` / `other`).

**Outputs** go under `./downloads` and `./output` relative to the **current working directory** (where you run the command), not inside `src/`.

#### About `--check` vs `--url`

- **`--check`**: Prints CUDA, MPS, RAM, Demucs device, and warnings. It does **not** run the same FFmpeg / torchcodec setup as a real `--url` run, and it does **not** download audio. If `--check` looks fine but `--url` fails with FFmpeg or codec-related errors, confirm **step 2** and the [torchcodec install notes](https://github.com/pytorch/torchcodec#installing-torchcodec).
- **`--url`**: Applies bundled-path FFmpeg (`static-ffmpeg` when needed) and shared-lib paths for torchcodec, then downloads and separates. Use this for a true end-to-end test after dependencies are in place.

### Packaged or downloaded “app” installs

This repository documents **installing from a Git clone** (venv + `requirements.txt` + system FFmpeg as above). If you ship a **standalone app** (installer, zip, or portable bundle), you must document (or script) your own **Python runtime**, **venv or embedded deps**, **FFmpeg + shared libraries**, and **model cache** layout — that flow is **not** automated in this repo.

### CLI reference

| Flag        | Description                                     |
| ----------- | ----------------------------------------------- |
| `--check`   | Print CUDA, RAM, and warnings; no download      |
| `--url URL` | YouTube URL to process                          |
| `--stem`    | Optional: `vocals`, `drums`, `bass`, or `other` |

### Desktop app (Tauri)

Run via `pnpm dev` or the built `.app`. Unlike the CLI, **all outputs are stored in the OS app-data directory**, not the current working directory.

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/com.ytsplit.app/yt-split/` |
| Windows | `%APPDATA%\com.ytsplit.app\yt-split\` |
| Linux | `~/.local/share/com.ytsplit.app/yt-split/` |

Directory layout:

```
yt-split/
├── downloads/          # raw yt-dlp mp3
└── projects/
    ├── <uuid>.json     # project metadata (title, URL, device, stem mode)
    └── <uuid>/
        └── stems/      # separated wav files
```

**Upgrading from a Phase 1 or Phase 2 build:** previous results remain in `./output/` under the repository root and will not appear in the Library automatically. Move them manually or reprocess the URLs.

### Tests

```bash
pytest
```
