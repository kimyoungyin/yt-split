# 프로덕션 패키징 + 크로스플랫폼 빌드 — Phase 4 (Master Plan)

> **상태:** Draft v0.1 (master plan)
> **선행:** [Phase 3](./phase-3.md)
> **다음:** [Phase 5 — CI/배포 + 코드 서명](./roadmap.md)

이 문서는 Phase 4의 마스터 플랜이다. Phase 3과 동일한 구조(Context → 결정 → 슬라이스 → 검증 → Quirks)를 사용한다. 슬라이스 단위(P4-A ~ P4-D)로 쪼개 각 슬라이스가 독립적인 `/pwrc-plan → /pwrc-work → /pwrc-review` 사이클로 돌 수 있게 한다.

---

## Context

Phase 1~3은 **개발 환경에서만 작동하는 파이프라인**이었다.

1. **`sidecar_path()`가 `CARGO_MANIFEST_DIR`에 고정되어 있다.** `pnpm build:app`으로 만든 `.app` 안에서 이 경로는 존재하지 않으므로 사이드카 spawn이 즉시 실패한다 ([sidecar.rs:75-81](../src-tauri/src/sidecar.rs)).
2. **`bundle.resources`가 비어 있다.** 사이드카 onedir 폴더(`src-tauri/binaries/<triple>/`)가 `.app` 번들에 포함되지 않는다 ([tauri.conf.json:34](../src-tauri/tauri.conf.json)).
3. **torchcodec용 FFmpeg 공유 라이브러리 탐색이 시스템 경로만 본다.** Homebrew 없는 사용자 머신에서는 `ensure_shared_ffmpeg_for_torchcodec()`이 아무것도 설정하지 않는다. PyInstaller 번들(`_MEIPASS`)에 이미 dylib을 복사해뒀지만 Python 코드가 이를 탐색 후보로 포함하지 않는다 ([ffmpeg_env.py](../src/features/ffmpeg_env.py)).
4. **Windows 사이드카 취소가 미구현이다.** Phase 3에서 플레이스홀더 에러로 남겼다 ([sidecar.rs:206-210](../src-tauri/src/sidecar.rs)).
5. **Windows/Linux 빌드 스크립트가 없다.** `pyinstaller/build.sh`는 macOS/Linux 전용이며, Windows용 `build.ps1`이 없다. spec 파일도 Windows FFmpeg DLL 수집이 누락되어 있다 ([yt-split-py.spec:46-76](../pyinstaller/yt-split-py.spec)).

**Phase 4의 목표:** `pnpm build:app` 한 번으로 설치 가능한 `.app/.dmg/.exe/.msi/.AppImage`를 산출하고, macOS arm64·x86_64, Windows x86_64, Linux x86_64에서 분리·취소가 동작하게 한다.

---

## 확정된 결정

이 섹션은 **리뷰 라운드 후 잠긴(locked) 결정**만 적는다.

- **sidecar_path() 분기:** `cfg!(debug_assertions)` 컴파일 분기를 사용한다. debug(dev) → `env!("CARGO_MANIFEST_DIR")/binaries/yt-split-py-<triple>/<exe>`, release(prod) → `app.path().resource_dir()?/binaries/yt-split-py-<triple>/<exe>`. `sidecar_binary_dir_from_resource(res: &Path) -> PathBuf` 순수 함수를 추출해 단위 테스트 가능하게 한다.
- **bundle.resources 스테이징:** `build.sh` / `build.ps1`가 이미 `src-tauri/binaries/<triple>/`에 스테이징한다. `tauri.conf.json`에서 `"binaries/yt-split-py-<triple>/**"` glob으로 해당 디렉터리를 번들에 포함한다. 각 플랫폼의 CI/빌드 머신은 자기 triple만 존재하므로, 없는 triple의 glob은 Tauri가 무시한다.
- **\_MEIPASS FFmpeg fallback:** `_search_dirs_ffmpeg_lib()`에 `sys._MEIPASS` (PyInstaller 번들 루트)를 **첫 번째 후보**로 추가한다. 이로써 Homebrew 없는 배포 머신에서도 번들된 dylib/dll을 사용한다.
- **Windows 취소:** `CREATE_NEW_PROCESS_GROUP` 플래그로 사이드카를 spawn하고, 취소 시 `GenerateConsoleCtrlEvent(CTRL_C_EVENT, pgid)` → 5초 대기 → `TerminateProcess` fallback 순서로 처리한다. `windows-sys` crate 추가.
- **macOS x86_64:** PyTorch 휠이 아키텍처별로 분리되어 universal2 빌드가 불가능하다. x86_64는 별도 머신(Rosetta 2 또는 x86_64 native runner)에서 별도 빌드한다. Phase 4에서 문서화하고, CI 자동화는 Phase 5에서 처리한다.
- **Windows build.ps1 신설:** `build.sh`와 동일한 스테이징 로직을 PowerShell로 작성한다. Windows FFmpeg "full-shared" DLL (`avutil-*.dll` 등)을 spec에서 수집한다.

---

## 슬라이스

Phase 4는 다음 4개 슬라이스로 쪼갠다. **A → B → (C, D 병렬 가능)** 순서 권장.

| #        | 슬라이스                                          | 핵심 결과                                                | 의존   |
| -------- | ------------------------------------------------- | -------------------------------------------------------- | ------ |
| **P4-A** | sidecar_path() dev/prod 분기 + \_MEIPASS fallback | prod 빌드에서 사이드카 경로 해석 + FFmpeg 탐색 로직 정상 | (없음) |
| **P4-B** | bundle.resources + macOS arm64 패키징 검증        | `pnpm build:app` → `.app` 설치 → 분리 1회 성공 (arm64)   | P4-A   |
| **P4-C** | Windows 지원 (cancel + build)                     | Windows `.exe/.msi`에서 분리·취소 동작                   | P4-A   |
| **P4-D** | Linux x86_64 패키징                               | Linux `.AppImage`에서 분리 1회 성공                      | P4-A   |

---

## 슬라이스 P4-A — sidecar_path() dev/prod 분기 + \_MEIPASS FFmpeg fallback

### 변경 파일

| 경로                                                                        | 변경                                                                                                                                                                                                                                           |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src-tauri/src/sidecar.rs`](../src-tauri/src/sidecar.rs)                   | `sidecar_binary_dir_from_resource(res: &Path) -> PathBuf` 추출. `sidecar_path()` → dev/prod 분기: debug → 기존 `CARGO_MANIFEST_DIR` 로직, release → `app.path().resource_dir()?` 기반. `run_pipeline`에 `app: AppHandle` 참조 추가(이미 있음). |
| [`src/features/ffmpeg_env.py`](../src/features/ffmpeg_env.py)               | `_search_dirs_ffmpeg_lib()`: `sys._MEIPASS` 속성이 있으면 `Path(sys._MEIPASS)`를 후보 목록 맨 앞에 추가.                                                                                                                                       |
| [`tests/features/test_ffmpeg_env.py`](../tests/features/test_ffmpeg_env.py) | `test_ensure_shared_ffmpeg_uses_meipass_first` 추가.                                                                                                                                                                                           |

### 첫 실패 테스트 (P4-A 1차 사이클)

**Rust 테스트** (`src-tauri/src/sidecar.rs` 내 `#[cfg(test)]`):

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn sidecar_binary_dir_prod_uses_resource_subpath() {
        let resource_dir = PathBuf::from("/fake/resources");
        let dir = sidecar_binary_dir_from_resource(&resource_dir);
        assert_eq!(
            dir,
            PathBuf::from("/fake/resources")
                .join("binaries")
                .join(format!("yt-split-py-{}", target_triple()))
        );
    }
}
```

현재 fail: `sidecar_binary_dir_from_resource` 함수가 존재하지 않아 컴파일 에러.

**Python 테스트** (`tests/features/test_ffmpeg_env.py`):

```python
def test_ensure_shared_ffmpeg_uses_meipass_first(monkeypatch, tmp_path):
    """PyInstaller 번들(_MEIPASS)이 있으면 해당 경로를 DYLD_LIBRARY_PATH에 먼저 추가한다."""
    import sys as _sys
    import os

    (tmp_path / "libavutil.60.dylib").touch()
    monkeypatch.setattr(_sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(_sys, "platform", "darwin")
    monkeypatch.delenv("DYLD_LIBRARY_PATH", raising=False)

    from src.features.ffmpeg_env import ensure_shared_ffmpeg_for_torchcodec
    ensure_shared_ffmpeg_for_torchcodec()

    dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
    parts = [p for p in dyld.split(os.pathsep) if p]
    assert str(tmp_path) == parts[0], f"_MEIPASS가 첫 번째여야 한다, 실제: {parts}"
```

현재 fail: `_search_dirs_ffmpeg_lib()`에 `_MEIPASS` 탐색 로직이 없어 `DYLD_LIBRARY_PATH`가 설정되지 않음.

### Done

- Rust: `sidecar_binary_dir_from_resource` 단위 테스트 통과
- Rust: `cargo check` 통과 (debug + release profile)
- Python: `test_ensure_shared_ffmpeg_uses_meipass_first` 통과
- Python: 기존 `test_ensure_shared_ffmpeg_prepends_brew_ffmpeg_lib_to_dyld_on_darwin` 회귀 없음

### 검증 명령

```bash
pytest tests/features/test_ffmpeg_env.py -v
(cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" cargo check)
(cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" cargo test)
```

---

## 슬라이스 P4-B — bundle.resources + macOS arm64 패키징 검증

### 변경 파일

| 경로                                                         | 변경                                                                                                                                                                                          |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json)  | `bundle.resources`에 각 triple glob 추가: `"binaries/yt-split-py-aarch64-apple-darwin/**"`, `"binaries/yt-split-py-x86_64-apple-darwin/**"` 등 4개. 존재하지 않는 triple glob은 Tauri가 무시. |
| [`README.md`](../README.md) 또는 `docs/build.md` (신규 선택) | 빌드 순서 문서화: ① `bash pyinstaller/build.sh` (사이드카 빌드) → ② `pnpm --dir ui install` → ③ `pnpm build:app`.                                                                             |

### 인터페이스 노트

- **실행권한 보존:** Tauri의 `bundle.resources`는 파일 권한(executable bit)을 보존한다. `build.sh`가 스테이징하는 `yt-split-py` 바이너리의 `chmod +x`가 `.app` 안에서도 유지되는지 P4-B 검증 단계에서 수동 확인한다.
- **resource_dir 경로:** macOS `.app`에서 `app.path().resource_dir()` → `<앱명>.app/Contents/Resources`. `binaries/yt-split-py-aarch64-apple-darwin/yt-split-py`가 그 아래에 위치해야 한다.
- **assetProtocol scope:** Phase 3에서 `$APPLOCALDATA/yt-split/**`로 이미 좁혀져 있다. WAV 파일 로드는 이 범위 안이므로 변경 불필요.

### 첫 실패 테스트 (P4-B 1차 사이클)

자동화 테스트 없음. 현재 실패 상태 = `pnpm build:app` 후 `.app`을 실행하면 "사이드카 바이너리를 찾을 수 없습니다" 에러.

**수동 검증 절차:**

1. `bash pyinstaller/build.sh` (arm64 사이드카 빌드, 이미 완료된 경우 스킵)
2. `pnpm build:app`
3. `.app`을 `Applications`로 이동 후 실행
4. URL 입력 → 분리 시작 → `~/Library/Application Support/com.ytsplit.app/yt-split/projects/<uuid>/stems/*.wav` 4개 생성 확인
5. Player에서 WAV 재생 확인 (assetProtocol WAV 로드)

### Done

- `pnpm build:app` 빌드 성공 (경고 없음)
- `.app` 실행 → 분리 1회 → stems 4개 생성
- Library 패널에 항목 표시 → 클릭 → Player 재생
- `yt-split-py` 바이너리 권한 확인: `ls -la <앱>.app/Contents/Resources/binaries/yt-split-py-aarch64-apple-darwin/yt-split-py` → `-rwxr-xr-x`

---

## 슬라이스 P4-C — Windows 지원 (취소 + 빌드)

### 변경 파일

| 경로                                                              | 변경                                                                                                                                                                                                     |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src-tauri/Cargo.toml`](../src-tauri/Cargo.toml)                 | `[target.'cfg(windows)'.dependencies]`에 `windows-sys = { version = "0.52", features = ["Win32_System_Threading", "Win32_Foundation", "Win32_Console"] }` 추가.                                          |
| [`src-tauri/src/sidecar.rs`](../src-tauri/src/sidecar.rs)         | `run_pipeline` Windows 분기: `Command`에 `creation_flags(CREATE_NEW_PROCESS_GROUP)` 적용. `cancel_pipeline` Windows 구현: `GenerateConsoleCtrlEvent` → 5s poll → `TerminateProcess` fallback.            |
| `pyinstaller/build.ps1` (신규)                                    | `build.sh`와 동일한 스테이징 로직. `$triple = "x86_64-pc-windows-msvc"`, `pyinstaller yt-split-py.spec`, `dist\yt-split-py → dist\yt-split-py-$triple → src-tauri\binaries\yt-split-py-$triple`.         |
| [`pyinstaller/yt-split-py.spec`](../pyinstaller/yt-split-py.spec) | `_ffmpeg_lib_dir()` Windows 분기 추가: FFmpeg "full-shared" 빌드의 `bin/*.dll` 탐색 경로 (예: `C:\ffmpeg\bin`). `binaries`에 `avutil-*.dll`, `avcodec-*.dll`, `avformat-*.dll`, `swresample-*.dll` 추가. |
| [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json)       | `bundle.resources`에 `"binaries/yt-split-py-x86_64-pc-windows-msvc/**"` glob 추가 (P4-B에서 함께 처리 가능).                                                                                             |

### Windows 취소 구현 노트

```rust
// spawn 시 (Windows 전용)
#[cfg(windows)]
{
    use std::os::windows::process::CommandExt;
    cmd.creation_flags(0x00000200); // CREATE_NEW_PROCESS_GROUP
}

// cancel 시 (Windows 전용)
#[cfg(windows)]
fn cancel_windows(pid: u32) -> Result<(), String> {
    use windows_sys::Win32::Console::GenerateConsoleCtrlEvent;
    use windows_sys::Win32::System::Threading::{
        OpenProcess, TerminateProcess, WaitForSingleObject,
        PROCESS_TERMINATE, INFINITE,
    };

    // 1. Ctrl+C to process group
    unsafe { GenerateConsoleCtrlEvent(0 /*CTRL_C_EVENT*/, pid) };

    // 2. Wait up to 5s
    let handle = unsafe { OpenProcess(PROCESS_TERMINATE, 0, pid) };
    if handle != 0 {
        let result = unsafe { WaitForSingleObject(handle, 5000) };
        if result != 0 {
            // 3. Force kill if still alive
            unsafe { TerminateProcess(handle, 1) };
        }
        unsafe { windows_sys::Win32::Foundation::CloseHandle(handle) };
    }
    Ok(())
}
```

### FFmpeg Windows spec 노트

```python
# pyinstaller/yt-split-py.spec 내 _ffmpeg_lib_dir() Windows 분기
if sys.platform == "win32":
    candidates = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c

# DLL 수집 (libav*, libsw*, libpost* → 번들 루트)
ffmpeg_dir = _ffmpeg_lib_dir()
if ffmpeg_dir:
    for pattern in ("avutil-*.dll", "avcodec-*.dll", "avformat-*.dll",
                    "swresample-*.dll", "swscale-*.dll", "postproc-*.dll"):
        for f in glob.glob(os.path.join(ffmpeg_dir, pattern)):
            binaries.append((f, "."))
```

### 첫 실패 테스트 (P4-C 1차 사이클)

현재 `cancel_pipeline` Windows 구현:

```rust
#[cfg(windows)]
pub async fn cancel_pipeline(...) -> Result<(), String> {
    Err("Windows에서의 사이드카 취소는 Phase 4 패키징 단계에서 추가 예정".into())
}
```

구현 후 이 에러 문자열이 사라지고 `windows-sys` 기반 로직으로 대체된다. **컴파일 테스트:**

```bash
# Windows 빌드 머신 또는 cross-compile 환경에서
cargo build --target x86_64-pc-windows-msvc
```

현재 실패: `windows-sys` 의존성 없음 + `cancel_pipeline` Windows 구현 누락.

### Done

- `cargo build --target x86_64-pc-windows-msvc` 성공 (경고 없음)
- `build.ps1` 실행 → `src-tauri\binaries\yt-split-py-x86_64-pc-windows-msvc\` 스테이징 완료
- Windows `.exe`에서 URL 입력 → 분리 → stems 생성
- 분리 중 취소 → 프로세스 종료 확인 (Task Manager에서 `yt-split-py.exe` 사라짐)

### 검증 명령 (Windows 머신)

```powershell
.\pyinstaller\build.ps1
cd src-tauri; cargo build --target x86_64-pc-windows-msvc
pnpm build:app
```

---

## 슬라이스 P4-D — Linux x86_64 패키징

### 변경 파일

| 경로                                                              | 변경                                                                                                                     |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| [`pyinstaller/yt-split-py.spec`](../pyinstaller/yt-split-py.spec) | Linux 탐색 경로 검증 (이미 `/usr/lib/x86_64-linux-gnu` 등 있음). `.so` 탐색 패턴이 `libav*.so.*`를 올바르게 잡는지 확인. |
| [`pyinstaller/build.sh`](../pyinstaller/build.sh)                 | Linux 실행 검증 (이미 `Linux-x86_64` 분기 있음). 권한(chmod +x) 스테이징 확인.                                           |
| [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json)       | `bundle.resources`에 `"binaries/yt-split-py-x86_64-unknown-linux-gnu/**"` glob 추가 (P4-B에서 함께 처리 가능).           |

### 인터페이스 노트

- **Linux AppImage:** Tauri v2의 `targets: "all"` 설정 시 Linux에서 `.AppImage` + `.deb` 산출. Phase 4는 `.AppImage`를 일차 검증 대상으로 한다.
- **시스템 libavutil.so:** Linux에서는 `/usr/lib/x86_64-linux-gnu/libavutil.so.*` 등을 번들에 포함한다. spec 파일이 이미 `/usr/lib/x86_64-linux-gnu` 경로를 탐색하지만, 배포판마다 경로가 다를 수 있어 `ldconfig -p` 파이프라인으로 보완 가능하다 (OD-3).

### 첫 실패 테스트 (P4-D 1차 사이클)

자동화 테스트 없음. 현재 실패 = Linux 머신에서 `.AppImage` 실행 시 사이드카를 찾지 못함 (bundle.resources 미설정, P4-B에서 해결 예정).

**수동 검증 절차 (Ubuntu 22.04 x86_64):**

1. `pip install -r requirements.txt && bash pyinstaller/build.sh`
2. `pnpm --dir ui install && pnpm build:app`
3. `.AppImage` 실행 → URL 입력 → 분리 → stems 생성 확인

### Done

- `.AppImage` 실행 성공
- 분리 1회 → `~/.local/share/com.ytsplit.app/yt-split/projects/<uuid>/stems/*.wav` 확인
- Library → Player 재생 확인
- (선택) `.deb` 설치 후 동일 동작 확인

---

## 결과 (각 슬라이스 완료 시 채움)

- [ ] P4-A 머지: sidecar_path() prod 분기 + \_MEIPASS fallback
- [ ] P4-B 머지: macOS arm64 .app 패키징 검증 완료
- [ ] P4-C 머지: Windows 분리·취소 동작 + build.ps1
- [ ] P4-D 머지: Linux .AppImage 검증 완료

---

## Open decisions (리뷰 라운드용)

| #        | 항목                                     | 옵션                                                                                                 | 현재 추천                                                                                                                                    | 상태         |
| -------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| **OD-1** | Windows 취소 방식                        | (a) `GenerateConsoleCtrlEvent` + `TerminateProcess` fallback (b) Job Object (c) `TerminateProcess`만 | **(a)**. Python signal handler가 없으므로 graceful이 필수는 아니나, Ctrl+C가 더 안전하다.                                                    | **Locked**   |
| **OD-2** | bundle.resources glob 전략               | (a) 4개 triple glob 모두 나열 (b) 스테이징 폴더(`src-tauri/resources/`) 경유 단일 glob               | **(a)**. 없는 triple glob은 Tauri가 무시. 단순함 우선.                                                                                       | **Locked**   |
| **OD-3** | Linux FFmpeg so 탐색 강화                | (a) 현행 하드코딩 경로 (b) `ldconfig -p` 파이프라인으로 동적 탐색                                    | **(b)** 추천. `distro` 패키지나 `subprocess.check_output(["ldconfig", "-p"])`로 보완.                                                        | **Open**     |
| **OD-4** | macOS x86_64 빌드 자동화                 | (a) Phase 4에서 문서화만 (b) Phase 4에서 Rosetta 2 머신 수동 빌드 가이드 (c) Phase 5 CI에 위임       | **(a)+(b)**. x86_64 runner에서 빌드 절차를 문서화하고, CI 자동화는 Phase 5로.                                                                | **Deferred** |
| **OD-5** | Demucs 모델 가중치 번들 여부             | (a) 사용자 첫 실행 시 다운로드 (~2GB, 현행) (b) 앱 번들에 포함 (앱 크기 +2GB)                        | **(a)**. 번들 크기 급증 대비 효용 없음. 첫 실행 시 진행 표시 UI 개선은 Phase 5+ polish.                                                      | **Locked**   |
| **OD-6** | `pnpm build:app` 전 사이드카 빌드 자동화 | (a) `beforeBuildCommand`에 `bash pyinstaller/build.sh` 추가 (b) 별도 단계로 문서화                   | **(b)**. 사이드카 빌드는 5~10분 + Python 환경 필요. `beforeBuildCommand`로 자동화하면 항상 재빌드되어 느림. Phase 5 CI에서 캐싱과 함께 처리. | **Locked**   |
| **OD-7** | Windows FFmpeg DLL 소스                  | (a) 사용자가 FFmpeg "full-shared" 사전 설치 + spec이 탐색 (b) build.ps1이 FFmpeg 자동 다운로드       | **(a)**. 빌드 머신에서 한 번만 설치. CI는 GitHub Actions `choco install ffmpeg`.                                                             | **Locked**   |

리뷰 시 각 OD에 ✅/✏️ 코멘트 + 선택 이유를 남겨주세요.
상태 정의: **Open**(결정 필요), **Deferred**(후속 슬라이스/Phase로 이관), **Locked**(현재 라운드에서 잠금).

---

## P4-A+B 우선 구현 체크리스트 (완료 시 체크)

### 0) OD 잠금 (구현 전)

- [ ] **OD-1 잠금:** Windows 취소 방식 확정
- [ ] **OD-2 잠금:** bundle.resources glob 전략 확정
- [ ] **OD-5 잠금:** 모델 가중치 번들 미포함 확정
- [ ] **OD-6 잠금:** 빌드 단계 분리(수동) 확정
- [ ] **OD-7 잠금:** Windows FFmpeg DLL 소스 확정

### 1) P4-A 구현

- [x] `sidecar_binary_dir_from_resource(res: &Path) -> PathBuf` 함수 추출
- [x] `sidecar_path()` debug/release 분기 적용
- [x] `run_pipeline`이 release 모드에서 `resource_dir`로 경로를 해석하는지 확인 (`cargo check --release` 통과)
- [x] `_search_dirs_ffmpeg_lib()`에 `sys._MEIPASS` 첫 후보 추가
- [x] Rust 단위 테스트 `sidecar_binary_dir_prod_uses_resource_subpath` 통과
- [x] Python 단위 테스트 `test_ensure_shared_ffmpeg_uses_meipass_first` 통과

### 2) P4-B 구현

- [ ] `tauri.conf.json` `bundle.resources` 4개 triple glob 추가
- [ ] `pnpm build:app` 빌드 성공 (macOS arm64)
- [ ] `.app` 설치 후 분리 1회 실행 성공
- [ ] stems 4개 + 메타 `.json` 생성 확인 (AppLocalData)
- [ ] Player WAV 재생 확인 (assetProtocol)
- [ ] 실행권한 보존 확인 (`-rwxr-xr-x`)

### 3) P4-C 구현 (Windows 머신)

- [ ] `Cargo.toml`에 `windows-sys` 의존성 추가
- [ ] `run_pipeline` Windows spawn에 `CREATE_NEW_PROCESS_GROUP` 추가
- [ ] `cancel_pipeline` Windows 구현 (GenerateConsoleCtrlEvent → TerminateProcess)
- [ ] `build.ps1` 작성 + 실행 확인
- [ ] spec Windows FFmpeg DLL 수집 추가
- [ ] `cargo build --target x86_64-pc-windows-msvc` 성공
- [ ] `.exe/.msi` 분리·취소 수동 검증

### 4) P4-D 구현 (Linux 머신)

- [ ] `tauri.conf.json`에 Linux triple glob 확인 (P4-B에서 함께 처리)
- [ ] Ubuntu 22.04에서 `bash pyinstaller/build.sh` 성공
- [ ] `.AppImage` 분리 1회 수동 검증

### 5) 검증/문서 동기화

- [ ] `pytest tests/features/test_ffmpeg_env.py tests/features/test_project.py tests/app/test_pipeline.py -v` 통과
- [ ] `(cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" cargo test)` 통과
- [ ] `pnpm --dir ui test` 통과 (회귀 없음)
- [ ] `build.sh` / `build.ps1` + `pnpm build:app` 순서 README 문서화
- [ ] 이 문서의 `## 결과` 체크박스 갱신

---

## Risks

- **실행권한 소실:** `tauri.conf.json`의 `bundle.resources` glob은 파일을 복사한다. macOS `.app` 번들러가 `yt-split-py` 바이너리의 execute bit를 보존하지 않으면 spawn이 `Permission denied`로 실패한다. P4-B 수동 검증에서 `ls -la` 로 확인하고, 필요 시 build.rs에서 `chmod +x`를 후처리로 추가한다.
- **DYLD_LIBRARY_PATH SIP 제한:** macOS 시스템 무결성 보호(SIP) 환경에서 서명된 `.app`의 자식 프로세스는 `DYLD_LIBRARY_PATH`가 스트립될 수 있다. 그러나 Tauri app → PyInstaller sidecar의 경우 사이드카 자체 bootloader가 `_MEIPASS`를 `DYLD_LIBRARY_PATH`에 추가한 뒤 Python을 시작하므로, Python 코드의 `ensure_shared_ffmpeg_for_torchcodec()` 호출 시점에는 이미 경로가 설정된 상태이다. Phase 4 검증에서 실제 서명 없는 `.app`으로 먼저 확인한다.
- **Windows long path:** yt-dlp / torch가 긴 경로 + 한글 경로에서 실패할 수 있다. `AppLocalData` = `%LOCALAPPDATA%\com.ytsplit.app\` — 경로에 한글 포함 가능. Python 코드는 `pathlib.Path`만 사용 중이나, yt-dlp 내부 `os.path` 사용처를 확인한다.
- **Windows FFmpeg DLL 버전 충돌:** 사이드카 빌드 머신의 FFmpeg 버전과 사용자 시스템의 FFmpeg 버전이 다르면 DLL 로드 충돌이 발생할 수 있다. 번들에 포함한 DLL이 우선 탐색되도록 `_MEIPASS` 경로 우선 정책(P4-A)과 연동한다.
- **Tauri `$APPLOCALDATA` 변수 플랫폼 차이:** macOS `~/Library/Application Support/<identifier>`, Windows `%LOCALAPPDATA%\<identifier>`, Linux `~/.local/share/<identifier>`. `app.path().app_local_data_dir()`의 반환값을 각 플랫폼에서 실제 확인한다.
- **Demucs 모델 첫 다운로드 네트워크 의존:** 첫 분리 시 `~/.cache/torch/hub/` 아래에 htdemucs 모델(~2GB)을 다운로드한다. 오프라인 환경에서는 실패한다. Phase 4 범위 밖이지만 README에 명시한다.
- **macOS x86_64 빌드 미검증:** Rosetta 2 또는 x86_64 native 머신이 없으면 P4-B와 동일한 검증을 할 수 없다. Phase 4에서 절차를 문서화하고 실제 검증은 Phase 5 CI에서 처리한다.

---

## Lessons applied

`~/.claude/lessons/Users-kim-young-yin-Documents-codes-yt-split/`: **none yet** (Phase 3 사이클에서 생성 예정).

---

## Quirks (작업 중 채움)

| 증상                         | 원인 | 해결 |
| ---------------------------- | ---- | ---- |
| _슬라이스 진행하며 채워나감_ |      |      |

---

## 향후 진행

- **Phase 5** — GitHub Actions matrix 빌드 + tag push 시 자동 release + macOS Developer ID 서명/공증 + Windows (선택) EV 서명.

---

## GSTACK REVIEW REPORT

| Review        | Trigger               | Why                             | Runs | Status | Findings |
| ------------- | --------------------- | ------------------------------- | ---- | ------ | -------- |
| CEO Review    | `/plan-ceo-review`    | Scope & strategy                | 0    | -      | not run  |
| Codex Review  | `/codex review`       | Independent 2nd opinion         | 0    | -      | not run  |
| Eng Review    | `/plan-eng-review`    | Architecture & tests (required) | 0    | -      | not run  |
| Design Review | `/plan-design-review` | UI/UX gaps                      | 0    | -      | not run  |
| DX Review     | `/plan-devex-review`  | Developer experience gaps       | 0    | -      | not run  |

- **UNRESOLVED:** 0
- **VERDICT:** DRAFT — 리뷰 미실시. P4-A 구현 착수 전 Eng Review 권장.
