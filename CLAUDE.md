# Audio-Separator-AI Project Rules

## Project Overview

High-performance local utility for extracting audio from YouTube URLs and separating them into individual stems (Vocals, Drums, Bass, Other) using Meta's Demucs AI. Enables users to obtain full multi-track sessions for any song.

## Tech Stack

- Core: Python 3.10+, PyTorch
- Libraries: yt-dlp, demucs, ffmpeg-python
- Architecture: Feature-Sliced Design (FSD)

## Directory Structure

- `src/app`: Application entry point (`main.py`)
- `src/features`: Core logic domains
- `download`: YouTube audio extraction
- `separation`: AI model inference
- `system`: Environment and hardware validation
- `src/shared`: Utilities (IO, logging, constants)
- `output/`: Processed stems (`{video_title}/{track_name}.mp3`)

## Critical: Hardware Validation Logic

System check via src/features/system is mandatory before execution:

1. CUDA Check: Verify `torch.cuda.is_available()`.
    - If missing: Warn user about CPU fallback and significant latency (10-20m per song). Require confirmation.

2. RAM/VRAM Check:
    - GPU: 4GB+ VRAM recommended.
    - System: Warn if RAM < 8GB to prevent OOM crashes.

3. Storage Check: Ensure space for model weights (~2GB) and high-quality output files.

## Development Rules

- Naming: Snake_case for functions/vars, PascalCase for classes.

- Separation: Default to 4-stem mode (Vocals, Drums, Bass, Other). Support single-stem filtering.

- Error Handling: Capture subprocess stderr; provide user-friendly error messages.

- Typing: Mandatory Python type hinting for all functions.

## Key Commands

- `python main.py --url [URL]`: Full separation

- `python main.py --url [URL] --stem [vocal|drums|bass]`: Target specific stem

- `python main.py --check`: Diagnostic mode

- `pip install -r requirements.txt`: Dependency setup
