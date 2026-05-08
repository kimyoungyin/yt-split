# CI/배포 + 코드 서명 — Phase 5 (Master Plan)

> **상태:** Draft v0.1 (master plan)
> **선행:** [Phase 4](./phase-4.md)
> **다음:** Phase 6 — UI polish + 오프라인 모델 캐시 (미정)

이 문서는 Phase 5의 마스터 플랜이다. Phase 4와 동일한 구조(Context → 결정 → 슬라이스 → 검증 → Quirks)를 사용한다. 슬라이스 단위(P5-A ~ P5-D)로 쪼개 각 슬라이스가 독립적인 `/pwrc-plan → /pwrc-work → /pwrc-review` 사이클로 돌 수 있게 한다.

---

## Context

Phase 4는 **수동 빌드**로 설치 가능한 패키지를 만드는 것까지 완료했다.

1. **모든 빌드가 수동이다.** `bash pyinstaller/build.sh && pnpm build:app` 순서를 각 플랫폼 머신에서 직접 실행해야 한다. CI가 없으므로 PR마다 다른 플랫폼의 회귀를 잡을 방법이 없다.
2. **코드 서명/공증이 없다.** macOS에서 배포한 `.dmg`를 사용자가 열면 Gatekeeper가 "개발자를 확인할 수 없습니다" 경고를 표시한다. 사용자는 우클릭 → 열기로 우회해야 한다.
3. **릴리스 자동화가 없다.** 새 버전을 배포하려면 각 플랫폼에서 수동 빌드 → 파일을 직접 GitHub Release에 업로드해야 한다.
4. **앱 내 업데이트 알림이 없다.** 새 버전이 나와도 사용자가 직접 웹 페이지를 다시 방문해야 한다.
5. **P4-C/P4-D(Windows/Linux)가 CI 없이는 검증이 어렵다.** Windows/Linux 머신 없이는 코드 구현만 완료된 상태다.

**Phase 5의 목표:** GitHub Actions matrix 빌드로 PR마다 4개 플랫폼(macOS arm64, macOS x86_64, Windows, Linux) 빌드를 자동화하고, tag push 시 서명된 릴리스 아티팩트를 GitHub Release에 자동 첨부한다. 앱 내 업데이트 확인(tauri-plugin-updater)을 추가해 사용자가 항상 최신 버전을 받을 수 있게 한다.

---

## 확정된 결정

이 섹션은 **리뷰 라운드 후 잠긴(locked) 결정**만 적는다.

- **matrix 전략:** `macos-14`(arm64) + `macos-13`(Intel) + `ubuntu-22.04` + `windows-latest` 4개 runner. Rosetta 2 에뮬레이션 대신 macos-13 Intel native runner를 사용한다.
- **FFmpeg CI 설치:** macOS → `brew install ffmpeg`, Linux → `sudo apt-get install -y ffmpeg`, Windows → `choco install ffmpeg`. 각 runner에서 시스템 FFmpeg를 설치하면 PyInstaller spec의 `_ffmpeg_lib_dir()`가 번들에 DLL/dylib를 수집한다.
- **pip/cargo/pnpm 캐싱:** `requirements.txt` 해시(pip), `Cargo.lock` 해시(cargo registry + target), `ui/pnpm-lock.yaml` 해시(pnpm). 첫 빌드 후 30~60분 → 10분 이내로 단축.
- **Release 트리거:** `push: tags: ['v*.*.*']`. 빌드 workflow와 release workflow를 분리한다(`build.yml` + `release.yml`). `build.yml`은 모든 push/PR에서 실행하고, `release.yml`은 tag에서만 실행해 artifact를 GitHub Release에 첨부한다.
- **CHANGELOG:** 수동 작성. 프로젝트 규모에서 git-cliff 자동화는 과잉.
- **tauri-plugin-updater:** P5-D에서 구현. 앱 시작 시 자동으로 업데이트 확인 → 알림 배너 표시.
- **Windows EV 서명:** 제외(Open Decision OD-2). 비용($400+/yr) 대비 현 단계에서 필수 아님.
- **macOS 코드 서명:** OD-1로 판단 보류. 서명 여부에 따라 P5-B 슬라이스의 범위가 달라진다.

---

## 슬라이스

Phase 5는 다음 4개 슬라이스로 쪼갠다. **A → (B, C 병렬 가능) → D** 순서 권장.

| #        | 슬라이스                                  | 핵심 결과                                              | 의존   |
| -------- | ----------------------------------------- | ------------------------------------------------------ | ------ |
| **P5-A** | GitHub Actions CI 기본 파이프라인         | PR마다 4 OS artifact 빌드 + upload 성공                | (없음) |
| **P5-B** | macOS Developer ID 서명 + 공증            | `.dmg` Gatekeeper 통과 (OD-1 결정 필요)                | P5-A   |
| **P5-C** | tag push 자동 Release                     | `v*.*.*` tag → GitHub Release 자동 생성 + artifact 첨부 | P5-A   |
| **P5-D** | tauri-plugin-updater 자동 업데이트        | 앱 시작 시 업데이트 확인 → 알림 배너                   | P5-C   |

---

## 슬라이스 P5-A — GitHub Actions CI 기본 파이프라인

### 변경 파일

| 경로 | 변경 |
| ---- | ---- |
| `.github/workflows/build.yml` (신규) | matrix CI: checkout → Python/Node/Rust setup → FFmpeg 설치 → pip install → sidecar 빌드 → pnpm install → `pnpm build:app` → artifact upload |

### workflow 구조

```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-14
            target: aarch64-apple-darwin
            sidecar_cmd: bash pyinstaller/build.sh
          - os: macos-13
            target: x86_64-apple-darwin
            sidecar_cmd: bash pyinstaller/build.sh
          - os: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            sidecar_cmd: bash pyinstaller/build.sh
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            sidecar_cmd: pwsh pyinstaller/build.ps1
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: actions-rust-lang/setup-rust-toolchain@v1
        with: { toolchain: stable }
      - uses: pnpm/action-setup@v3
        with: { version: 9 }

      # FFmpeg (각 플랫폼)
      - name: Install FFmpeg (macOS)
        if: runner.os == 'macOS'
        run: brew install ffmpeg
      - name: Install FFmpeg (Linux)
        if: runner.os == 'Linux'
        run: sudo apt-get install -y ffmpeg libgtk-3-dev libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf
      - name: Install FFmpeg (Windows)
        if: runner.os == 'Windows'
        run: choco install ffmpeg -y

      # 캐시
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-${{ hashFiles('requirements.txt') }}
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            src-tauri/target
          key: cargo-${{ runner.os }}-${{ hashFiles('src-tauri/Cargo.lock') }}
      - uses: actions/cache@v4
        with:
          path: ui/node_modules
          key: pnpm-${{ runner.os }}-${{ hashFiles('ui/pnpm-lock.yaml') }}

      # 빌드
      - run: pip install -r requirements.txt
      - run: ${{ matrix.sidecar_cmd }}
      - run: pnpm --dir ui install
      - run: pnpm build:app

      # Artifact 업로드
      - uses: actions/upload-artifact@v4
        with:
          name: yt-split-${{ matrix.target }}
          path: |
            src-tauri/target/release/bundle/dmg/*.dmg
            src-tauri/target/release/bundle/nsis/*.exe
            src-tauri/target/release/bundle/msi/*.msi
            src-tauri/target/release/bundle/appimage/*.AppImage
            src-tauri/target/release/bundle/deb/*.deb
          if-no-files-found: ignore
```

### 인터페이스 노트

- **Linux 의존 패키지:** Tauri v2 Linux 빌드에 `libgtk-3-dev libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf` 필요. `apt-get install`을 FFmpeg 설치와 한 줄로 합친다.
- **Windows PowerShell 스크립트:** `pwsh pyinstaller/build.ps1`. `pwsh`(PowerShell Core)가 `windows-latest`에 기본 설치됨.
- **사이드카 빌드 시간:** PyTorch + Demucs 의존성 설치에 5~15분, PyInstaller 번들링에 3~5분. 캐시 미스 시 첫 빌드 40~60분 예상.
- **cargo target 캐시 크기:** Tauri 빌드 후 `src-tauri/target` 수GB 가능. GitHub Actions 캐시 10GB 한도 유의 — `release/` 하위만 선택 캐싱 고려.

### 첫 실패 테스트 (P5-A 1차 사이클)

현재 실패 상태 = `.github/workflows/build.yml`이 없어 PR 시 CI가 전혀 동작하지 않음.

**수동 검증 절차:**
1. 브랜치 push 또는 PR 생성
2. GitHub Actions 탭에서 `Build` workflow 실행 확인
3. 4개 job이 모두 `success`인지 확인
4. Artifacts 섹션에서 `yt-split-aarch64-apple-darwin` 등 파일 다운로드 확인

### Done

- `build.yml` 커밋 후 PR 시 4개 runner 모두 green
- 각 artifact에서 플랫폼별 설치 파일 포함 확인
- 캐시 적중 후 빌드 시간 10분 이내

---

## 슬라이스 P5-B — macOS Developer ID 서명 + 공증

> **OD-1 결정 필요.** Apple Developer Program 계정이 없으면 이 슬라이스 전체를 건너뛰고 서명 없이 배포한다 (사용자가 우클릭 → 열기로 Gatekeeper 우회).

### 변경 파일

| 경로 | 변경 |
| ---- | ---- |
| `src-tauri/tauri.conf.json` | `bundle.macOS.signingIdentity`, `bundle.macOS.providerShortName`, `bundle.macOS.entitlements` 추가 |
| `src-tauri/entitlements.plist` (신규) | hardened runtime + network-client entitlement |
| `pyinstaller/yt-split-py.spec` | `codesign_identity` 환경변수 기반 설정 (`APPLE_SIGNING_IDENTITY`) |
| `.github/workflows/build.yml` | macOS runner에 인증서 import + notarization step 추가 |

### macOS 서명/공증 구현 노트

**로컬 선행 작업 (CI 투입 전 필수):**
1. Apple Developer Program 등록 → Developer ID Application 인증서 발급 + `.p12` 내보내기
2. App Store Connect API key 생성 (Key ID, Issuer ID, `.p8` 파일)
3. `tauri.conf.json`에 `signingIdentity` 설정 후 `pnpm build:app` 로컬 공증 1회 통과 확인

**entitlements.plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
  <true/>
  <key>com.apple.security.network.client</key>
  <true/>
</dict>
</plist>
```

> `allow-unsigned-executable-memory`: PyTorch JIT / torchcodec 런타임 코드 생성에 필요. hardened runtime 기본 설정이 이를 막으면 sidecar가 segfault.

**tauri.conf.json 추가 (macOS 전용):**
```json
{
  "bundle": {
    "macOS": {
      "signingIdentity": null,
      "entitlements": "../src-tauri/entitlements.plist"
    }
  }
}
```
> `signingIdentity: null` → 환경변수 `APPLE_SIGNING_IDENTITY`를 Tauri가 자동 읽음. 로컬에서는 `.env`로 주입, CI에서는 secret으로 주입.

**CI secrets (GitHub Repository Settings → Secrets):**
```
APPLE_CERTIFICATE             # base64 인코딩된 .p12
APPLE_CERTIFICATE_PASSWORD    # .p12 암호
APPLE_SIGNING_IDENTITY        # "Developer ID Application: NAME (TEAMID)"
APPLE_ID                      # Apple ID 이메일
APPLE_TEAM_ID                 # 10자리 팀 ID
APPLE_API_KEY_ID              # App Store Connect API Key ID
APPLE_API_KEY_ISSUER_ID       # App Store Connect Issuer ID
APPLE_API_PRIVATE_KEY         # .p8 파일 내용 (base64)
```

**CI 인증서 import step:**
```yaml
- name: Import Apple Certificate
  if: runner.os == 'macOS' && env.APPLE_CERTIFICATE != ''
  env:
    APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
    APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
  run: |
    echo "$APPLE_CERTIFICATE" | base64 --decode > certificate.p12
    security create-keychain -p "" build.keychain
    security default-keychain -s build.keychain
    security unlock-keychain -p "" build.keychain
    security import certificate.p12 -k build.keychain -P "$APPLE_CERTIFICATE_PASSWORD" -T /usr/bin/codesign
    security set-key-partition-list -S apple-tool:,apple: -s -k "" build.keychain
```

**PyInstaller spec 서명:**
```python
# yt-split-py.spec
import os
codesign_identity = os.environ.get("APPLE_SIGNING_IDENTITY", None)
```

**sidecar 바이너리 별도 서명 확인:** Tauri `bundle.resources`에 포함된 `yt-split-py` 바이너리는 Tauri 빌드 시 자동으로 재서명된다. 그러나 PyInstaller onedir 내부 `.dylib`들이 ad-hoc 서명만 있을 경우 notarization 거부될 수 있다 — spec의 `codesign_identity`로 사전 서명 필수.

### 수동 검증 (OD-1이 (a)일 때)

```bash
# 빌드 후 서명 확인
codesign -dv --verbose=4 "yt-split.app"
spctl -a -v "yt-split.app"   # "accepted" 확인

# 공증 확인
xcrun stapler validate "yt-split.dmg"
```

### Done

- `spctl -a -v yt-split.app` → `source=Notarized Developer ID` 출력
- 다른 Mac(개발자 계정 없는 기기)에서 더블클릭 → Gatekeeper 경고 없이 실행
- CI macOS runner에서 서명/공증 step 완료

---

## 슬라이스 P5-C — tag push 자동 Release

### 변경 파일

| 경로 | 변경 |
| ---- | ---- |
| `.github/workflows/release.yml` (신규) | `v*.*.*` tag push 트리거 → build matrix → GitHub Release 생성 + artifact 첨부 |
| `src-tauri/tauri.conf.json` | `version` 필드 tag와 동기화 확인 (수동 또는 스크립트) |
| `CHANGELOG.md` (신규 or 기존) | 릴리스 노트 수동 작성 규칙 |

### release.yml 구조

```yaml
name: Release

on:
  push:
    tags: ['v*.*.*']

jobs:
  build:
    # build.yml과 동일한 matrix strategy
    # ...
    steps:
      # ... (build.yml과 동일한 빌드 단계)
      - uses: actions/upload-artifact@v4
        with:
          name: yt-split-${{ matrix.target }}
          path: ...

  release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts/
          merge-multiple: true
      - uses: softprops/action-gh-release@v2
        with:
          files: artifacts/**
          body_path: CHANGELOG.md   # 또는 tag message
          draft: false
          prerelease: ${{ contains(github.ref_name, '-') }}  # v0.2.0-beta → prerelease
```

### 버전 동기화 전략

- `src-tauri/tauri.conf.json`의 `version` 필드를 릴리스 전에 수동으로 bump.
- 순서: `tauri.conf.json` version 업데이트 → commit → `git tag v0.x.x` → `git push origin v0.x.x`
- Phase 5에서는 수동 bump. Phase 6+에서 `release-plz`/`cargo-release` 자동화 고려.

### 첫 실패 테스트 (P5-C 1차 사이클)

현재 실패 상태 = `.github/workflows/release.yml`이 없어 tag push 시 아무것도 일어나지 않음.

**수동 검증 절차:**
```bash
# tauri.conf.json version을 "0.2.0"으로 업데이트 후
git add src-tauri/tauri.conf.json
git commit -m "chore: bump version to 0.2.0"
git tag v0.2.0
git push origin v0.2.0
```
→ GitHub Actions `Release` workflow 실행 확인 → GitHub Releases 페이지에서 .dmg/.exe/.AppImage 첨부 확인.

### Done

- `v*.*.*` tag push 후 4개 플랫폼 artifact가 GitHub Release에 자동 첨부
- macOS `.dmg`(서명 후), Windows `.exe`+`.msi`, Linux `.AppImage`+`.deb` 포함
- prerelease 태그(`v0.2.0-beta`) → `Pre-release` 마크 자동 적용

---

## 슬라이스 P5-D — tauri-plugin-updater 자동 업데이트

### 변경 파일

| 경로 | 변경 |
| ---- | ---- |
| `src-tauri/Cargo.toml` | `tauri-plugin-updater` 의존성 추가 |
| `src-tauri/src/lib.rs` | `.plugin(tauri_plugin_updater::Builder::new().build())` 등록 |
| `src-tauri/src/updater.rs` (신규) | `check_update` Tauri command: 업데이트 확인 → 메타 반환 |
| `src-tauri/tauri.conf.json` | `plugins.updater.pubkey` + `endpoints` 설정 |
| `ui/src/features/updater/` (신규) | FSD slice: `api/updater.ts`, `model/store.ts`, `ui/UpdateBanner.tsx` |
| `.github/workflows/release.yml` | `latest.json` 파일을 GitHub Release에 함께 첨부 |

### 업데이트 플로우

```
앱 시작
  └→ Rust: check_update command
       └→ tauri-plugin-updater가 endpoints[0] 폴링
            └→ GitHub Release latest.json 파싱
                 ├─ 최신 버전 == 현재 버전: 아무것도 안 함
                 └─ 최신 버전 > 현재 버전:
                      └→ emit("update-available", { version, body, ... })
                           └→ React: UpdateBanner 표시
                                └→ 사용자 클릭 → 다운로드 + 설치
```

### 서명 키 페어 생성

```bash
# 개발 머신에서 1회 실행
pnpm tauri signer generate -w ~/.tauri/yt-split.key
# 출력: 공개키 (tauri.conf.json에 넣음) + 비밀키 (CI secret으로)
```

**CI secret 추가:**
```
TAURI_SIGNING_PRIVATE_KEY         # ~/.tauri/yt-split.key 내용
TAURI_SIGNING_PRIVATE_KEY_PASSWORD  # 비밀키 암호 (없으면 빈 문자열)
```

### tauri.conf.json 추가

```json
{
  "plugins": {
    "updater": {
      "active": true,
      "pubkey": "<pnpm tauri signer generate 출력 공개키>",
      "endpoints": [
        "https://github.com/kimyoungyin/yt-split/releases/latest/download/latest.json"
      ]
    }
  }
}
```

### latest.json 구조

```json
{
  "version": "0.2.0",
  "notes": "업데이트 내용",
  "pub_date": "2026-06-01T00:00:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "<release 시 자동 생성>",
      "url": "https://github.com/.../yt-split_0.2.0_aarch64.dmg"
    },
    "darwin-x86_64": { ... },
    "windows-x86_64": { ... },
    "linux-x86_64": { ... }
  }
}
```

> `release.yml`에서 `tauri-action` 또는 커스텀 스크립트로 `latest.json`을 자동 생성해 Release에 첨부한다.

### UpdateBanner UI (React)

```tsx
// ui/src/features/updater/ui/UpdateBanner.tsx
// 앱 상단에 표시. "v0.2.0 업데이트 가능 — 지금 설치" 버튼
// 설치 클릭 시 → 다운로드 진행 표시 → 재시작 요청
```

### Done

- 앱 시작 시 `latest.json` 폴링 (네트워크 없으면 조용히 실패)
- 최신 버전 있으면 앱 상단 UpdateBanner 표시
- "지금 설치" 클릭 → 다운로드 → 재시작 → 새 버전으로 실행 확인

---

## 결과 (각 슬라이스 완료 시 채움)

- [ ] P5-A 머지: 4 OS matrix CI 파이프라인 green
- [ ] P5-B 머지: macOS 서명/공증 + Gatekeeper 통과 (OD-1 결정 후)
- [ ] P5-C 머지: tag push → GitHub Release 자동 생성
- [ ] P5-D 머지: 앱 내 업데이트 확인 동작

---

## Open decisions (리뷰 라운드용)

| #        | 항목                                     | 옵션                                                                                                              | 현재 추천                                                                                                                                     | 상태       |
| -------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| **OD-1** | macOS 코드 서명/공증 방식                | (a) Apple Developer Program($99/yr) + Developer ID + notarytool 공증 (b) 서명 없음 (우클릭 → 열기로 우회)         | **(a)** 권장. 더블클릭 즉시 실행. macOS 15+에서 공증 없는 앱 정책 점점 엄격. 단, 계정/비용 없으면 (b)도 허용.                                 | **Open**   |
| **OD-2** | Windows EV 서명                          | (a) 포함 (b) 제외                                                                                                 | **(b)**. EV 인증서 $400+/yr. 현 단계 생략. 사용자 확정.                                                                                      | **Locked** |
| **OD-3** | Release CHANGELOG 방식                   | (a) 수동 작성 (b) git-cliff 자동화                                                                                | **(a)**. 프로젝트 규모에서 자동화 과잉.                                                                                                       | **Locked** |
| **OD-4** | PyTorch/사이드카 cargo target 캐시 범위  | (a) `src-tauri/target` 전체 캐시 (b) `src-tauri/target/release/` 하위만                                          | **(b)**. GitHub Actions 캐시 10GB 한도. 전체 캐시는 debug 빌드 산출물 포함 → 빠르게 한도 초과.                                               | **Locked** |
| **OD-5** | macOS x86_64 runner 선택                 | (a) macos-13 Intel native (b) macos-14-xlarge (Rosetta 2) (c) macos-14 standard (arm64 only, 별도 x86 빌드 없음) | **(a)**. macos-13 = Intel native. Rosetta 빌드는 실제 x86 환경과 다를 수 있음.                                                                | **Locked** |
| **OD-6** | notarization 방식 (OD-1이 (a)일 때)      | (a) notarytool + App Store Connect API key (b) altool                                                             | **(a)**. altool deprecated (Xcode 14+에서 제거).                                                                                             | **Locked** |
| **OD-7** | tauri-plugin-updater 업데이트 체크 시점  | (a) 앱 시작 시 자동 (b) 설정 메뉴에서 수동 트리거                                                                | **(a)**. 사용자 편의. 실패 시 조용히 무시.                                                                                                    | **Locked** |
| **OD-8** | latest.json 자동 생성 방식               | (a) `tauri-action` GitHub Action 사용 (b) 커스텀 Python/jq 스크립트                                              | **(a)**. `tauri-action`이 서명 + latest.json 생성을 한 번에 처리. 단, tauri-action이 전체 빌드를 담당하면 기존 build.sh 캐시와 충돌 주의.    | **Open**   |

리뷰 시 각 OD에 ✅/✏️ 코멘트 + 선택 이유를 남겨주세요.
상태 정의: **Open**(결정 필요), **Deferred**(후속 슬라이스/Phase로 이관), **Locked**(현재 라운드에서 잠금).

---

## P5-A+C 우선 구현 체크리스트 (완료 시 체크)

### 0) OD 잠금 (구현 전)

- [ ] **OD-1 잠금:** macOS 코드 서명 여부 확정 (Apple Developer Program 계정 유무 확인)
- [x] **OD-2 잠금:** Windows EV 서명 제외 확정
- [x] **OD-3 잠금:** CHANGELOG 수동 작성 확정
- [x] **OD-4 잠금:** cargo target 캐시 범위 확정 (release/ 하위)
- [x] **OD-5 잠금:** macOS x86_64 runner = macos-13 확정
- [x] **OD-6 잠금:** notarytool 방식 확정 (OD-1이 (a)일 때)
- [x] **OD-7 잠금:** updater 자동 체크 확정
- [ ] **OD-8 잠금:** latest.json 생성 방식 확정 (tauri-action vs 커스텀)

### 1) P5-A 구현

- [x] `.github/workflows/build.yml` 생성
- [x] 4개 runner matrix 설정 (macos-14, macos-13, ubuntu-22.04, windows-latest)
- [x] 각 runner FFmpeg 설치 step (macOS: brew, Linux: apt + Tauri 의존성, Windows: choco)
- [x] pip/cargo/pnpm 캐싱 설정 (pip: setup-python cache:pip 내장, cargo: restore-keys 추가, pnpm: ui/node_modules)
- [x] 사이드카 빌드 step (macOS/Linux: `bash build.sh`, Windows: `pwsh build.ps1`)
- [x] `pnpm build:app` step
- [x] artifact upload step (플랫폼별 설치 파일, if-no-files-found: ignore)
- [ ] PR 생성 → 4개 runner 모두 green 확인 (실제 GitHub push 필요)

### 2) P5-B 구현 (OD-1이 (a)일 때)

- [ ] Apple Developer Program 계정 확인 + Developer ID 인증서 발급
- [ ] App Store Connect API key 생성 (Key ID, Issuer ID, .p8)
- [ ] `src-tauri/entitlements.plist` 생성
- [ ] `tauri.conf.json`에 `bundle.macOS.entitlements` 추가
- [ ] 로컬 서명/공증 1회 통과 확인 (`spctl -a -v *.app`)
- [ ] GitHub secrets 설정 (APPLE_CERTIFICATE, APPLE_SIGNING_IDENTITY 등)
- [ ] `build.yml` macOS 인증서 import + 서명 step 추가
- [ ] CI macOS artifact: `spctl` 검증 통과

### 3) P5-C 구현

- [ ] `.github/workflows/release.yml` 생성
- [ ] `v*.*.*` tag push 트리거 설정
- [ ] build matrix (build.yml과 동일)
- [ ] artifact download + GitHub Release 생성 (`softprops/action-gh-release`)
- [ ] `tauri.conf.json` version bump + tag 동기화 절차 문서화
- [ ] `git tag v0.2.0 && git push origin v0.2.0` → GitHub Release 자동 생성 확인
- [ ] prerelease 태그 동작 확인 (v0.2.0-beta → Pre-release 마크)

### 4) P5-D 구현

- [ ] `src-tauri/Cargo.toml`에 `tauri-plugin-updater` 추가
- [ ] `src-tauri/src/lib.rs`에 플러그인 등록
- [ ] `pnpm tauri signer generate`로 키 페어 생성
- [ ] `tauri.conf.json`에 `plugins.updater.pubkey` + `endpoints` 설정
- [ ] `src-tauri/src/updater.rs` command 구현 (`check_update`)
- [ ] `ui/src/features/updater/` FSD slice 생성 (api, model, ui)
- [ ] UpdateBanner 컴포넌트 구현
- [ ] `release.yml`에 `latest.json` 생성 + 첨부 step 추가
- [ ] 새 Release 배포 후 이전 버전 앱에서 UpdateBanner 노출 확인

### 5) 검증/문서 동기화

- [ ] `pnpm --dir ui test` 통과 (UpdateBanner 회귀 없음)
- [ ] `(cd src-tauri && cargo test)` 통과
- [ ] README.md에 CI 배지 추가 (`![Build](https://github.com/.../workflows/Build/badge.svg)`)
- [ ] 이 문서의 `## 결과` 체크박스 갱신
- [ ] 빌드/릴리스 순서 README 문서화 (개발자용)

---

## Risks

- **Apple notarization 첫 시도 실패:** entitlements 누락, hardened runtime 미적용, 내부 `.dylib` 미서명 등 다양한 원인. 로컬에서 `notarytool submit` 통과 후 CI에 옮기는 순서 필수. CI에서 처음 시도하면 디버그에 시간이 많이 걸린다.
- **PyInstaller onedir 내부 dylib 서명 미흡:** `yt-split-py` 바이너리 자체는 `codesign`으로 서명되지만, onedir 내 `_internal/*.dylib`들이 ad-hoc 서명만 있으면 notarization 거부. `yt-split-py.spec`의 `codesign_identity`를 환경변수로 주입해 PyInstaller가 서명하도록 해야 한다.
- **GitHub Actions runner 디스크 부족:** PyTorch + Demucs 의존성이 ~3GB, cargo target ~4GB, sidecar bundle ~411MB. ubuntu-22.04 runner는 기본 14GB, macOS runner는 14GB. `actions/cache`에서 오래된 캐시가 쌓이면 공간 부족 가능. `cargo clean` 또는 release/ 하위만 캐시하는 전략 필요.
- **빌드 시간 초과:** GitHub Actions 무료 플랜은 job당 6시간 제한. PyTorch + sidecar 빌드가 첫 실행 시 60분 이상 가능. 캐시 미스 + 느린 runner 조합이면 timeout 가능. `fail-fast: false`로 다른 runner는 계속 진행.
- **tauri-plugin-updater 서명 키 노출:** `TAURI_SIGNING_PRIVATE_KEY` secret이 유출되면 악성 업데이트 배포 가능. GitHub secret 관리 주의. 키 교체 시 `tauri.conf.json`의 `pubkey`도 함께 업데이트해야 이전 버전 앱이 새 업데이트를 신뢰.
- **latest.json URL 경로 변경:** GitHub 레포지토리 이름/소유자 변경 시 `endpoints` URL이 깨짐. 별도 도메인(`updates.ytsplit.app`)으로 redirect하는 방법 고려.
- **macOS Gatekeeper 정책 강화 (OD-1 (b) 선택 시):** macOS 15 이후 공증 없는 앱 실행 허용 정책이 더 엄격해질 수 있음. 우클릭 우회가 언제까지 가능할지 보장 없음.
- **P4-C/P4-D CI 최초 실패 가능성:** Windows/Linux에서 처음으로 CI가 돌면 Phase 4에서 예상치 못한 이슈가 나올 수 있음(경로, 권한, DLL 버전). P5-A 구현 직후 첫 CI 실행에서 P4-C/P4-D 코드를 함께 검증하는 기회가 된다.

---

## Quirks (작업 중 채움)

| 증상 | 원인 | 해결 |
| ---- | ---- | ---- |
| pip cache가 macOS/Windows runner에서 미적중 (빌드 성공이지만 매번 전체 재다운로드) | `~/.cache/pip` 하드코딩은 Linux 전용 경로. macOS 실제 경로: `~/Library/Caches/pip`, Windows: `%LOCALAPPDATA%\pip\Cache`. 침묵 속에 실패하므로 발견하기 어렵다. | `actions/setup-python`의 `cache: "pip"` 내장 파라미터로 대체. 플랫폼별 경로를 자동 처리한다. 수동 `actions/cache` + 하드코딩 경로는 제거. |

---

## 향후 진행

- **Phase 6** — 오프라인 첫 실행 개선(모델 다운로드 진행 UI), UI polish, 웹 소개 페이지 배포.

---

## GSTACK REVIEW REPORT

| Review        | Trigger               | Why                             | Runs | Status | Findings |
| ------------- | --------------------- | ------------------------------- | ---- | ------ | -------- |
| CEO Review    | `/plan-ceo-review`    | Scope & strategy                | 0    | -      | not run  |
| Codex Review  | `/codex review`       | Independent 2nd opinion         | 0    | -      | not run  |
| Eng Review    | `/plan-eng-review`    | Architecture & tests (required) | 0    | -      | not run  |
| Design Review | `/plan-design-review` | UI/UX gaps                      | 0    | -      | not run  |
| DX Review     | `/plan-devex-review`  | Developer experience gaps       | 0    | -      | not run  |

- **UNRESOLVED:** 2 (OD-1 macOS 서명 여부, OD-8 latest.json 생성 방식)
- **VERDICT:** DRAFT — 리뷰 미실시. P5-A 구현 착수 전 Eng Review 권장.
