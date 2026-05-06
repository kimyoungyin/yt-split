# 멀티트랙 플레이어 + 디자인 시스템 — Phase 2

## Context

[Phase 1](./phase-1.md)에서 Tauri v2 + Rust ↔ Python 사이드카 채널이 macOS arm64에서 검증됐다. Demucs 분리가 끝나면 `stage.done` 이벤트가 4개 stem의 절대경로 dict를 `usePipelineStore.tracks`로 흘려보내는 데까지가 동작한다. 그러나 UI는 인라인 스타일로 path 텍스트만 나열했고, 사용자에게 핵심 가치(세션을 들을 수 있음)는 노출되지 않았다.

**Phase 2의 목표:** 그 절대경로 dict를 동시 재생 가능한 멀티트랙 플레이어로 변환하고, 동시에 prototype UI를 shadcn/ui + Tailwind + Lucide로 production 톤까지 끌어올린다. 부수적으로 Phase 2 검증 중 가장 자주 마주칠 사용성 이슈("URL 잘못 넣고 분리 시작 → 5~30분 못 멈춤")를 막기 위해 사이드카 취소도 같이 처리한다 ([roadmap.md:157-158](./roadmap.md) 권장).

**확정된 결정:**
- 재생 엔진은 **Web Audio API 직접** (`AudioContext` + `AudioBufferSourceNode` + `GainNode`). howler.js는 4-track 동기 제어 자유도가 떨어져 채택하지 않음.
- 디자인 시스템은 **Tailwind v3 + shadcn/ui (CLI init) + lucide-react**. v4는 Vite 플러그인이 베타-안정 사이라 안정 노선.
- **Solo는 single mode** (radio-button 시맨틱). 마지막 클릭한 stem만 단일 재생. 같은 stem 재클릭 시 해제. 초기 plan은 OR(DAW 표준)이었으나 실사용 후 single이 더 직관적이라 변경. mute는 multi-toggle, solo와 직교.
- 파일 접근은 `convertFileSrc`(asset protocol). `tauri.conf.json`의 `app.security.assetProtocol.scope`에 출력 디렉토리 패턴 등록. capabilities는 손대지 않음(Tauri v2의 asset protocol은 capability 시스템 밖에서 동작).
- Waveform 시각화는 이번 Phase 제외. decode된 buffer가 메모리에 있어 차후 추가 쉬움.
- 사이드카 취소는 Rust에서 `tokio::process::Child`의 pid를 보관, `cancel_pipeline` command가 `libc::kill(pid, SIGTERM)` 발송. Python은 SIGTERM 핸들러로 final `error` + `done` 이벤트를 emit한 뒤 종료. 라이브러리/AppLocalData 전환은 Phase 3.

---

## 디렉터리 변경

Phase 1의 슬라이스에 `audio-player`를 추가하고 `shared/{ui,lib,styles}`를 새로 만든다. Python/Rust 쪽은 cancel 추가로 한정.

```
yt-split/
├── src/app/main.py                           # SIGTERM 핸들러 추가
├── src-tauri/
│   ├── Cargo.toml                            # libc (cfg(unix))
│   ├── tauri.conf.json                       # security.assetProtocol
│   └── src/
│       ├── lib.rs                            # manage(PipelineState) + cancel command 등록
│       └── sidecar.rs                        # PipelineState (pid Mutex), cancel_pipeline
├── ui/
│   ├── tailwind.config.cjs                   # shadcn 토큰
│   ├── postcss.config.cjs
│   ├── components.json                       # @/shared/ui, @/shared/lib/utils alias
│   └── src/
│       ├── shared/
│       │   ├── styles/globals.css            # @tailwind + CSS variables
│       │   ├── lib/utils.ts                  # cn(...)
│       │   └── ui/                           # shadcn (button/slider/card/toggle/...)
│       ├── features/
│       │   ├── audio-player/                 # 신규 슬라이스
│       │   │   ├── api/audio-engine.ts       # Web Audio 싱글톤
│       │   │   ├── api/auto-load.ts          # pipeline → player subscribe
│       │   │   ├── model/types.ts
│       │   │   ├── model/solo.ts             # effectiveGain 순수함수
│       │   │   ├── model/store.ts            # Zustand + rAF 시간 추적
│       │   │   ├── model/solo.test.ts        # vitest, 8 케이스
│       │   │   └── ui/{Player,Transport,TrackChannel}.tsx
│       │   └── separate-audio/
│       │       ├── api/sidecar.ts            # cancelPipeline export
│       │       └── ui/PipelineRunner.tsx     # shadcn 리팩토링 + Cancel
│       └── app/App.tsx                       # PipelineRunner + Player 합성
└── package.json                              # PATH=$HOME/.cargo/bin prefix
```

---

## 단계별 작업 (구현 순서)

### 1. Tailwind + shadcn 부트스트랩

`tailwindcss@^3 postcss autoprefixer @types/node tailwindcss-animate`(devDeps), `lucide-react clsx tailwind-merge class-variance-authority`(deps). `components.json`은 `@/shared/ui`, `@/shared/lib/utils`로 FSD 정합성 유지. `pnpm dlx shadcn@latest add button slider card toggle progress input select separator`로 8개 컴포넌트 install. 자동으로 Radix deps도 들어옴.

`vite.config.ts`에 `@/*` alias를 명시 추가 — 이전엔 tsconfig에만 있었고 vite는 동기화 안 됐음. `ui/src/main.tsx`에서 `@/shared/styles/globals.css` import.

`ui/package.json`은 `type: module`이라 tailwind/postcss config는 `.cjs` 확장자로 작성(ESM에서 `module.exports`/`require()` 충돌 회피).

### 2. Tauri assetProtocol

```jsonc
// src-tauri/tauri.conf.json
"security": {
  "csp": null,
  "assetProtocol": {
    "enable": true,
    "scope": ["$APPLOCALDATA/**", "**/output/**"]
  }
}
```

`Cargo.toml`은 이미 `tauri = { features = ["protocol-asset"] }`. capabilities는 변경 안 함 — Tauri v2의 asset protocol은 capability schema에 등장하지 않고 `assetProtocol` 설정으로만 제어됨. 실측: schema dump에 `core:asset:*` 권한 자체가 없음.

### 3. Audio engine + store

**모듈 싱글톤 패턴.** React 외부에서 `AudioContext` 1개를 유지, 트랙별 `AudioBuffer`/`GainNode`를 Map에 캐시, 재생 중에만 `AudioBufferSourceNode`를 생성·소비. `BufferSourceNode`는 1회용이라 매 play마다 새로 생성한다.

**동기 보장.** 4 source 모두 동일한 `start(when, offset)` 호출 — `when = ctx.currentTime + 0.05` cushion. WKWebView의 user gesture 정책 때문에 첫 play에서 `ctx.resume()`을 fire-and-forget으로 호출.

**시간 추적.**
```
playing ? ctx.currentTime - startedAtCtxTime + offsetAtStart : offsetAtStart
```
rAF 루프가 store의 `currentTime`을 0.05초 이상 차이날 때만 commit (60Hz 리렌더 회피).

**Solo single mode.** `store.toggleSolo`가 다른 채널의 `solo: false`를 강제. 같은 채널 재클릭 시 해제. `solo.effectiveGain` 함수 자체는 OR로 정의(여러 solo가 mathematically 들어와도 안전), store policy가 single을 강제. 8개 vitest 케이스(mute×solo×anySolo 조합).

**메모리 경고.** `loadTracks`가 디코드 후 `length × channels × 4 bytes` 합산, 300MB 초과 시 store.errorMessage에 경고 set. 재생은 계속.

### 4. UI 컴포넌트

`Player`(상태별 분기) → `Transport`(play/pause + seek slider + mm:ss) + `TrackChannel`(세로 슬라이더 + status 아이콘 + Mute/Solo 토글). 마스터 채널은 사용자 요청으로 제외(엔진의 masterGain 노드는 라우팅용으로 유지).

`shared/ui/slider.tsx`는 shadcn 기본이 horizontal만 가정해 vertical에서 트랙이 width 0으로 뭉개졌다. orientation 분기 추가:
```tsx
isVertical ? "h-full w-2" : "h-2 w-full"  // Track
isVertical ? "w-full"     : "h-full"      // Range
```

`TrackChannel`의 status 아이콘: 활성 = `Volume2`, mute(또는 다른 채널 solo로 무음) = `VolumeX`, solo 중 = `Headphones`. stem 라벨 옆에 작게.

### 5. 사이드카 취소

**Rust.** `PipelineState { pid: Mutex<Option<u32>> }`를 `app.manage(...)`. spawn 직후 pid 보관, `wait().await` 끝나면 클리어. `cancel_pipeline` command가 `libc::kill(pid as i32, SIGTERM)` 호출. Tokio의 `Child::start_kill()`은 SIGKILL이라 Python 핸들러가 발동 안 해 채택 안 함. Windows는 cancel 미구현(Phase 4로 이관) — `cfg(windows)` 분기에서 명시적 에러.

**Python.** `signal.signal(SIGTERM, ...)` 핸들러가 `emitter.error("pipeline", "사용자가 분리를 취소했습니다") + emitter.done(ok=False) + sys.exit(143)`. emitter가 enabled일 때만 등록.

**UI.** `PipelineRunner`의 Run 버튼이 `status==="running"`일 때 destructive variant `Cancel`로 변신. `cancelPipeline()`은 `invoke("cancel_pipeline")`.

### 6. PipelineRunner shadcn 리팩토링

인라인 스타일 → `Card` + `CardHeader/Content` + `Input` + `Select` + `Button` + `Progress`. Radix Select가 빈 string value를 거부하므로 `STEM_OPTIONS`의 첫 항목을 `"all"`로 변경하고 invoke 호출 시 `stem === "all" ? null : stem` 매핑.

### 7. 레이아웃 통합

`App.tsx`가 `PipelineRunner`와 `Player`를 동일 `Card` 톤으로 세로 배치(`mx-auto max-w-3xl space-y-4 p-6`). `useAutoLoadPlayer()` 훅이 `usePipelineStore.subscribe`로 `tracks` dict identity가 바뀔 때만 `usePlayerStore.load()` 호출(중복 로드 방지).

---

## 결과 (검증 통과)

- `pnpm --dir ui build` (tsc + vite): 285KB JS / 18KB CSS gzip
- `pnpm --dir ui test` (vitest): solo invariant 8/8
- `cargo check` (src-tauri): cancel 핸들러 + state manage 컴파일
- 실측: 짧은 곡(~30초) URL 분리 → done 직후 4채널 strip 자동 노출, 동시 재생 드리프트 없음, single solo / multi mute / seek / pause 모두 동작

**미해결 (Phase 3+로 이관):**
- 라이브러리/프로젝트 영속화/AppLocalData 이관 → Phase 3
- assetProtocol scope `**/output/**`은 dev 편의를 위한 임시. AppLocalData base로 좁힐 예정 → Phase 3
- 사이드카 취소 Windows 지원 → Phase 4 packaging
- Waveform 시각화 / EQ → 별도

---

## Quirks (Phase 2 작업 중 부딪힌 함정들)

| 증상 | 원인 | 해결 |
|------|------|------|
| `pnpm dev` 가 `cargo metadata` 호출에서 즉사 (`No such file or directory`) | pnpm이 spawn한 sh 자식이 zsh의 `~/.zshenv`(`. "$HOME/.cargo/env"`)를 source 못 함 | 루트 `package.json`의 모든 tauri 스크립트에 `PATH="$HOME/.cargo/bin:$PATH"` prefix 추가 |
| 세로 슬라이더에서 트랙이 안 보이고 thumb만 표시 | shadcn 기본 `slider.tsx`가 horizontal만 가정 (`Track`이 `h-2 w-full`) | `orientation` prop으로 Root/Track/Range 클래스 분기 |
| Radix Select가 `value=""` 옵션을 거부 | "empty value reserved for clearing selection" 정책 | "all stems"의 value를 `""` → `"all"`로 변경, invoke 시점에 null로 매핑 |
| `lucide-react@latest`가 1.14.0 (예상은 0.4xx) | 라이브러리가 1.x로 메이저 업그레이드됨 (2025 후반) | 모든 named export(`Play`, `Pause`, `VolumeX`, `Headphones`, `Volume2`)가 동일하게 살아있음을 확인하고 그대로 채택 |
| `vitest@latest`(4.1.5) 실행 시 `vite/module-runner` not exported | vitest 4가 vite 6+를 요구하는데 우리는 vite 5.4 | `pnpm add -D vitest@^2`로 다운그레이드 |
| Tauri v2 capability schema에 `core:asset:*`가 없음 | asset protocol은 v2에서 capability 시스템 밖, `tauri.conf.json`만으로 제어 | capabilities 손대지 않음. `protocol-asset` Cargo feature는 이미 활성 |
| pnpm dev에서 root `package.json` 옆 `node_modules` 미설치 경고 | root에 deps가 없어도 pnpm은 directory 존재 여부로 판단 | root에서 한 번 `pnpm install`(빈 install). lockfile/node_modules는 .gitignore의 `/node_modules/` `/pnpm-lock.yaml`로 무시 |
| `tokio::process::Child::start_kill()`이 SIGKILL이라 Python 핸들러 미발동 | tokio API의 의도된 동작 | unix에서 `libc::kill(pid, SIGTERM)` 직접 호출. `[target.'cfg(unix)'] libc = "0.2"` 추가 |

## 향후 진행

Phase 3는 [`docs/roadmap.md`](./roadmap.md)의 **프로젝트 라이브러리 + AppLocalData + 사이드카 취소(Windows)**. Phase 2의 assetProtocol scope과 Phase 1의 dev cwd 가정(workspace root)이 함께 정리될 예정.
