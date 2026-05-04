# Audio-Separator-AI Project Rules

## Project Overview

High-performance local utility for extracting audio from YouTube URLs and separating them into individual stems (Vocals, Drums, Bass, Other) using Meta's Demucs AI. Enables users to obtain full multi-track sessions for any song.

## Tech Stack

- Core: Python 3.10+, PyTorch
- Libraries: yt-dlp, demucs, ffmpeg-python, static-ffmpeg (bundled ffmpeg/ffprobe on `PATH` when processing `--url` if missing), torchcodec (with system FFmpeg shared libs for Demucs output; see Prerequisites)
- Architecture: Feature-Sliced Design (FSD)

## Prerequisites

- Run all CLI examples from the **repository root** so `src` imports resolve.
- **ffmpeg / ffprobe**: `pip install -r requirements.txt` pulls in **static-ffmpeg**. On `--url`, the app calls `static_ffmpeg.add_paths(weak=True)` so bundled binaries are used when nothing is on `PATH` (first use may download platform binaries; needs network). If you already have system ffmpeg, it stays preferred. `ffmpeg-python` alone does not ship the ffmpeg binary.
- **Demucs output (torchaudio / torchcodec)**: writing stems needs **FFmpeg shared libraries** (e.g. `libavutil`). On macOS run `brew install ffmpeg` (typical `lib` paths: Apple Silicon `/opt/homebrew/opt/ffmpeg/lib`, Intel Homebrew `/usr/local/opt/ffmpeg/lib`); the app prepends `DYLD_LIBRARY_PATH` when that directory exists. On Linux install the distro `ffmpeg` package (e.g. Debian/Ubuntu: `apt install ffmpeg`). See [README](./README.md) for Windows and links. `static-ffmpeg` alone does not replace these shared libs.
- After `pip install -r requirements.txt`, first run is slow while Demucs may download model weights (on the order of ~2GB disk for caches; keep headroom for outputs too).
- `src/features/system.py` refuses to run if free disk under the current working directory is below **5GB**.

## Directory Structure

- `src/app/main.py`: CLI entry (`python -m src.app.main` from repo root)
- `src/features/download`: YouTube audio extraction
- `src/features/ffmpeg_env`: Bundled ffmpeg via `static-ffmpeg` for `--url`, plus linker path for **torchcodec** (system FFmpeg `lib` dirs); `system_has_ffmpeg_shared_libs_for_torchcodec()` for detection
- `src/features/separation`: AI model inference (Demucs)
- `src/features/system`: Environment and hardware validation
- `downloads/`, `output/`: Created under **current working directory** when you run the app (not committed)
- `output/`: Processed stems (Demucs output layout under the chosen `-o` directory)

## Critical: Hardware Validation Logic

System check via `src/features/system` runs before processing a URL:

1. Accelerator for Demucs: resolve `demucs_device` in order **CUDA, then MPS (macOS Apple GPU via `torch.backends.mps`), else CPU**, and pass it to `demucs.separate` as `-d`. If the result is CPU only, warn about slow runtime and (with RAM or disk issues) require confirmation as today.

2. RAM/VRAM Check:
    - NVIDIA CUDA: VRAM as reported by PyTorch when CUDA is available.
    - macOS MPS: no separate VRAM figure in stats today; RAM still listed.
    - System: Warn if RAM < 8GB to prevent OOM crashes.

3. Storage Check: Ensure space for model weights (~2GB) and high-quality output files. Under 5GB free space blocks execution.

## Development Rules

- Naming: Snake_case for functions/vars, PascalCase for classes.

- Separation: Default to 4-stem mode (Vocals, Drums, Bass, Other). Support single-stem filtering.

- Error Handling: Capture subprocess stderr; provide user-friendly error messages.

- Typing: Mandatory Python type hinting for all functions.

## Key Commands

From the repository root:

- `pip install -r requirements.txt`: Dependency setup

- `python -m src.app.main --check`: Diagnostic mode (CUDA, RAM, warnings)

- `python -m src.app.main --url [URL]`: Full separation (all stems)

- `python -m src.app.main --url [URL] --stem [vocals|drums|bass|other]`: Target one stem pair (Demucs `--two-stems` mode)

- `python -m src.app.main --url [URL] --sidecar`: Sidecar mode (NDJSON one-line-per-event on stdout, used by the Tauri host)

---

## Tauri Desktop App (Phase 1 완료)

The Python pipeline above is also exposed as a sidecar binary embedded in a Tauri v2 + React desktop app. Phase 1 verified the end-to-end flow on macOS arm64; multi-track player, project library, shadcn UI, Windows/Linux builds, and CI are deferred. **See [`docs/phase-1.md`](./docs/phase-1.md) for the full plan, the implementation deltas, and the known quirks. [`docs/roadmap.md`](./docs/roadmap.md) sketches Phase 2~5 (player + design system, library + AppLocalData + cancel, prod packaging, CI/signing).**

### Architecture (Phase 1)

```
ui (Vite/React/Zustand, FSD)  ─── invoke / listen ───  src-tauri (Rust, tokio)
                                                              │
                                                              │ tokio::process::Command, current_dir = workspace root
                                                              ▼
                                          PyInstaller bundle: yt-split-py --sidecar
                                                              │
                                                              │ NDJSON on stdout (one event per line)
                                                              ▼
                                                ui store updates · stderr → logs
```

The sidecar is built by PyInstaller as a one-folder distribution under `src-tauri/binaries/yt-split-py-<target-triple>/`. Tauri's `externalBin` is **not** used because onedir is a folder, not a single binary; we spawn the binary directly with `tokio::process::Command` and pin its cwd to the workspace root so `downloads/` and `output/` land at the project root in dev. Production packaging via `bundle.resources` is a follow-up.

### Key directories beyond `src/`

- `pyinstaller/`: spec + `build.sh` (target-triple suffix staging)
- `src-tauri/src/sidecar.rs`: spawn + NDJSON line → `app.emit("yt-split:event", value)`; stderr → `yt-split:log`; exit code → `yt-split:done`
- `src-tauri/tauri.conf.json`: `frontendDist=../ui/dist`, `beforeDevCommand=pnpm --dir ui dev` (cwd is project root)
- `ui/src/features/separate-audio/`: FSD slice — `api/sidecar.ts` (idempotent listener via `globalThis` cache), `model/{events,store}.ts`, `ui/PipelineRunner.tsx`
- `docs/phase-1.md`: plan + result notes + quirk log

### Build and run

```bash
# 1. Python deps + sidecar bundle (~5–10 min, ~411 MB)
pip install -r requirements.txt
bash pyinstaller/build.sh

# 2. UI deps
pnpm --dir ui install

# 3. Dev (Vite + cargo run + window)
pnpm dev

# 4. Production app (after Phase 1)
pnpm build:app
```

### NDJSON event protocol

Stable across Phase 1+. Frontend types live in `ui/src/features/separate-audio/model/events.ts`; Python emits via `src/features/progress.py:ProgressEmitter`.

```
{"type":"hardware",        ...}                    # one-time, on startup
{"type":"stage",   "status":"start"|"done", ...}   # per stage (download / separate)
{"type":"progress","stage":..., "value":0..1}      # streamed
{"type":"error",   "stage":..., "message":...}
{"type":"done",    "ok":true|false}                # terminal
```

### Phase 1 quirks worth remembering before changing the pipeline

- The emitter writes to `sys.__stdout__`, not `sys.stdout`. demucs/yt-dlp prints are redirected to stderr inside `contextlib.redirect_stdout(sys.stderr)`; if the emitter used `sys.stdout` it would be redirected with them and the NDJSON channel would break.
- The Tauri listener attach is idempotent and cached on `globalThis` to survive React StrictMode's double-invoked dev `useEffect` and Vite HMR module re-evaluation. **Don't add a `useEffect` cleanup** for the sidecar listener — it races with StrictMode's sync cleanup against an async unlisten promise.
- numpy 2.x's `numpy.core` is a lazy alias over `numpy._core`; PyInstaller's static analysis misses the `.py` shim files. The spec explicitly `collect_submodules("numpy")` to keep `multiarray` resolvable.
- torchcodec's `libtorchcodec_coreN.dylib` files link to system FFmpeg by `@rpath`. We `collect_dynamic_libs("torchcodec")` and additionally stage Homebrew's `libav*/libsw*/libpost*.dylib` so the bundle resolves them from `_MEIPASS` at runtime.
