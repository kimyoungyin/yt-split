# Roadmap — Phase 2 이후

Phase 1은 [`docs/phase-1.md`](./phase-1.md)에서 마무리됐다. 아래는 Phase 2~5의
간단한 안내(stub). 각 Phase가 실제로 시작될 때 별도 `docs/phase-N.md`로
승격하면서 의도/결정/구현 노트를 채운다.

이 stub은 **무엇을 / 왜 / 어디서 시작 / 주의할 risk**만 짧게 적는다. 본격
설계는 Plan 모드에서 한다.

---

## Phase 2 — 멀티트랙 플레이어 + UI 디자인

**무엇을:** 분리된 4개 WAV(`vocals/drums/bass/other.wav`)를 한 화면에서 동시
재생하고 트랙별 volume/solo/mute를 제어하는 플레이어. 동시에 shadcn/ui +
Tailwind + Lucide를 도입해 Phase 1의 미니멀 UI를 production 수준으로 끌어올린다.

**왜:** Phase 1은 사이드카 채널만 검증했다. 사용자 가치(멀티트랙 세션)는
플레이어가 있어야 처음으로 드러난다.

**어디서 시작:**
- 새 슬라이스: `ui/src/features/audio-player/` (`api/`, `model/`, `ui/`).
- 재생 엔진은 Web Audio API (`AudioContext` + `AudioBufferSourceNode`)로
  샘플 정확 동기. `<audio>` 4개를 `play()` 동시 호출하는 방식은 drift가 있어
  비추천. (대안: `howler.js` — 내부적으로 Web Audio.)
- 트랙별 `GainNode`를 만들고 마스터 `GainNode`에 fan-in. `volume` 슬라이더는
  GainNode.gain.value, `solo`/`mute`는 boolean → gain 0/1 mapping.
- 분리 결과 트랙 경로(`Record<string,string>`)는 Phase 1 store에 이미 있음
  (`usePipelineStore.tracks`). Tauri `convertFileSrc`로 webview 접근 가능
  URL로 변환해 `fetch` → `AudioContext.decodeAudioData`.
- shadcn/ui 도입 후 `PipelineRunner`도 같은 스타일로 정리.

**Risk:**
- 4개 WAV decode + 메모리(곡당 ~128MB raw float). 긴 곡은 streaming 디코딩
  또는 lazy load 고려.
- macOS webview의 `convertFileSrc` 권한 — `tauri.conf.json` `app.security.assetProtocol`
  설정 필요.
- Solo가 여러 개일 때 의미 정의 (OR / 마지막 누른 것만).

---

## Phase 3 — 프로젝트 라이브러리 + AppLocalData + 사이드카 취소

**무엇을:** 한 번 처리한 곡들을 라이브러리로 누적하고, 다음 실행에서 다시
열 수 있게 한다. 출력 위치를 워크스페이스 루트 → 사용자별 AppLocalData로
옮기고, 진행 중인 사이드카를 UI에서 취소할 수 있게 한다.

**왜:** Phase 1·2는 단일 곡 워크플로우. 데스크톱 앱의 핵심 가치는 "내가
처리한 세션이 한 곳에 쌓이는 것"이다. 출력 경로도 dev 편의로 워크스페이스
루트에 두고 있으니 production을 향해 한 번 정리해야 한다.

**어디서 시작:**
- 새 슬라이스: `ui/src/entities/project/`, `ui/src/features/library/`.
- Rust 측: `tauri::path::PathResolver::app_local_data_dir()`로 base 경로
  결정. dev에서도 동일 위치 사용해 dev/prod 일관성 확보.
  사이드카 spawn 시 `current_dir`을 그 base의 `work/` 같은 하위로 변경.
- 메타데이터: `<base>/projects/<uuid>.json` (제목, URL, 생성 시각, device,
  트랙 경로). 디렉터리 스캔으로 라이브러리 리스트.
- 사이드카 취소: `tokio::process::Child`를 `tauri::State`로 보관하고
  `#[command] cancel_pipeline()`이 `child.kill().await`. Python 측은 SIGTERM에
  깔끔하게 종료되도록 demucs 호출 전후에 try/finally + `signal.signal`로
  cleanup hook.
- `tauri-plugin-fs`/`tauri-plugin-dialog` 추가 (capabilities scope 갱신).

**Risk:**
- `Path.cwd()` 의존을 제거해야 함 (`src/features/system.py:check_hardware_compatibility`,
  `src/app/main.py:run_pipeline`). 사이드카에 base path를 넘기는 인자 추가
  (`--workdir <path>`).
- macOS Sandbox / Hardened Runtime: AppLocalData 쓰기는 OK. 이후 Phase 5에서
  notarization 시 entitlements 다시 점검.
- Demucs 도중 SIGTERM 시 `_MEIPASS` 임시 디렉터리가 깨끗이 정리되는지 확인.

---

## Phase 4 — 프로덕션 패키징 + 크로스플랫폼 빌드

**무엇을:** `pnpm build:app`으로 설치 가능한 .app/.dmg/.exe/.AppImage를 산출.
macOS arm64만 검증된 Phase 1을 macOS x86_64, Windows x86_64, Linux x86_64로
확장한다.

**왜:** 사용자가 `bash pyinstaller/build.sh`나 `pnpm dev`를 직접 돌리는 건
개발자만 가능. 배포 가능한 형태가 있어야 다음 단계(CI/배포)로 갈 수 있다.

**어디서 시작:**
- 사이드카 onedir 폴더를 `tauri.conf.json` `bundle.resources`에 통째로 등록
  (또는 빌드 스크립트가 `src-tauri/resources/` 같은 staging 폴더로 복사한
  뒤 `bundle.resources`에서 그 경로 참조).
- `src-tauri/src/sidecar.rs`의 `sidecar_path()`를 dev/prod 분기:
  dev는 현재처럼 `CARGO_MANIFEST_DIR/binaries/...`,
  prod는 `app.path().resource_dir()? / "binaries" / "yt-split-py-..." / "yt-split-py"`.
- Windows spec:
  - `collect_dynamic_libs("torchcodec")` 그대로
  - FFmpeg "full-shared" 빌드의 DLL(`avutil-*.dll` 등)을 `binaries`에 추가
  - `_ffmpeg_lib_dir()`에 Windows 분기 추가
  - 출력 이름: `yt-split-py-x86_64-pc-windows-msvc/yt-split-py.exe`
- Linux spec: 시스템 `libavutil.so` 등을 `binaries`에 추가, AppImage 산출 검토.
- macOS x86_64는 별도 머신/CI에서 빌드. universal2는 PyTorch 의존성상 비추천
  (휠이 arch별로 분리).

**Risk:**
- macOS DYLD_LIBRARY_PATH는 SIP 때문에 `.app` 안에서 다르게 동작. PyInstaller
  bootloader가 `_MEIPASS`를 자동으로 dyld 경로에 추가하지만, `@rpath` 해석이
  실패하면 install_name_tool로 후처리 필요.
- Windows에서 yt-dlp/torch가 long path/한글 경로에 약함. `os.path` 대신 `pathlib`
  유지 + 사용자 홈 디렉터리에 한글이 있으면 검증.
- 번들 사이즈: macOS ~411MB, Windows/Linux도 비슷. 다운로드/설치 UX 안내 필요.

---

## Phase 5 — CI/배포 + 코드 서명

**무엇을:** GitHub Actions로 3 OS matrix 빌드 + tag push 시 자동 release.
macOS는 Developer ID 서명/공증, Windows는 (선택) EV 서명.

**왜:** 수동 빌드는 Phase 4까지로 충분. 사용자에게 신뢰할 수 있는 다운로드
링크를 제공하려면 서명 + 자동화가 필수.

**어디서 시작:**
- `.github/workflows/build.yml`: matrix `[macos-14, macos-13, ubuntu-latest,
  windows-latest]`. step 순서:
  1. checkout
  2. setup-python (3.10+) + setup-node + setup-rust
  3. `pip install -r requirements.txt`
  4. `bash pyinstaller/build.sh` (Windows는 `build.ps1` 별도)
  5. `pnpm --dir ui install`
  6. `pnpm build:app`
  7. artifacts upload
- 캐싱: pip wheel cache, cargo registry, target. 첫 빌드 후엔 큰 효과.
- macOS 서명: Apple Developer 계정 → Developer ID Application 인증서 → CI
  secret. `tauri.conf.json` `bundle.macOS.signingIdentity` 또는 환경변수
  `APPLE_SIGNING_IDENTITY`. Notarization은 `notarytool` (App Store Connect API
  key를 secret으로).
- Tag push에서 release: `softprops/action-gh-release` 등으로 .dmg/.exe/.AppImage
  첨부.
- (선택) `tauri-plugin-updater`: 서명 키 페어 생성 → `latest.json` host →
  앱이 자동 업데이트 확인.

**Risk:**
- Apple notarization은 첫 시도 실패율 높음 (entitlements, hardened runtime).
  로컬에서 한 번 통과시킨 뒤 CI에 옮기는 게 안전.
- PyTorch + sidecar 풀번들은 GitHub Actions runner의 디스크/시간 제한과
  부딪칠 수 있다. 첫 실행 시간 30~60분 가능 → cache로 단축.
- 사이드카 binary는 macOS notarization에서 별도 서명/스테이플 필요할 수
  있음 (외부 binary). PyInstaller bootloader + 내부 .dylib 모두 ad-hoc 서명
  되어 있는지 확인.

---

## 우선순위 / 순서

위 순서가 default 권장. 단,

- **Phase 2 → Phase 3 순서 입체바꾸기 가능**: 라이브러리(3) 없이도 플레이어(2)
  단독으로 가치 있음. 사용자 피드백 우선이면 Phase 2부터.
- **Phase 4와 5는 묶어서 가는 게 효율적**: prod 패키징과 CI는 한 머신/한 PR에서
  반복 검증해야 quirk를 잡기 쉽다.
- **Phase 3의 사이드카 취소만은 Phase 2와 동시에 처리 권장**: 분리 중 잘못된
  URL 등으로 길게 끄는 사용성 이슈가 Phase 2 검증 단계에서 바로 드러난다.
