# Audio-Separator-AI Project Rules

## Project Overview

High-performance local utility for extracting audio from YouTube URLs and separating them into individual stems (Vocals, Drums, Bass, Other) using Meta's Demucs AI. Enables users to obtain full multi-track sessions for any song.

## Tech Stack

- Core: Python 3.10+, PyTorch
- Libraries: yt-dlp, demucs, ffmpeg-python, static-ffmpeg (bundled ffmpeg/ffprobe on `PATH` when processing `--url` if missing)
- Architecture: Feature-Sliced Design (FSD)

## Prerequisites

- Run all CLI examples from the **repository root** so `src` imports resolve.
- **ffmpeg / ffprobe**: `pip install -r requirements.txt` pulls in **static-ffmpeg**. On `--url`, the app calls `static_ffmpeg.add_paths(weak=True)` so bundled binaries are used when nothing is on `PATH` (first use may download platform binaries; needs network). If you already have system ffmpeg, it stays preferred. `ffmpeg-python` alone does not ship the ffmpeg binary.
- After `pip install -r requirements.txt`, first run is slow while Demucs may download model weights (on the order of ~2GB disk for caches; keep headroom for outputs too).
- `src/features/system.py` refuses to run if free disk under the current working directory is below **5GB**.

## Directory Structure

- `src/app/main.py`: CLI entry (`python -m src.app.main` from repo root)
- `src/features/download`: YouTube audio extraction
- `src/features/ffmpeg_env`: Optional bundled ffmpeg/ffprobe via `static-ffmpeg` for `--url`
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
