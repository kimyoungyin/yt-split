# yt-split

Local pipeline: download audio from a YouTube URL with **yt-dlp**, separate stems with **Demucs** (`htdemucs`). See [CLAUDE.md](./CLAUDE.md) for project rules and hardware checks.

## Requirements

- Python 3.10+
- **static-ffmpeg** (declared in `requirements.txt`) supplies ffmpeg/ffprobe for yt-dlp and Demucs when your system does not. The first `--url` run may download those binaries. If `ffmpeg` is already on your `PATH`, that copy is used instead.
- **stem separation (Demucs)**: current PyTorch / `torchaudio` uses **torchcodec** to write audio files. On macOS, install FFmpeg **with shared libraries** so `libavutil` is available, for example `brew install ffmpeg` (Apple Silicon: `/opt/homebrew/opt/ffmpeg/lib`, Intel Homebrew: `/usr/local/opt/ffmpeg/lib`). The bundled `static-ffmpeg` binary is not a substitute for those shared libs. The CLI prepends that `lib` directory to `DYLD_LIBRARY_PATH` when it exists. On Linux, install the distro `ffmpeg` / `libavutil` package (e.g. Debian/Ubuntu: `apt install ffmpeg`) so the usual `lib` paths contain `libavutil`. On Windows, use an FFmpeg build that includes shared DLLs; see the [torchcodec install notes](https://github.com/pytorch/torchcodec#installing-torchcodec).

## Quick start

```bash
cd /path/to/yt-split
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.app.main --check
python -m src.app.main --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Outputs go under `./downloads` and `./output` in the directory from which you run the command.

## CLI reference

| Flag        | Description                                     |
| ----------- | ----------------------------------------------- |
| `--check`   | Print CUDA, RAM, and warnings; no download      |
| `--url URL` | YouTube URL to process                          |
| `--stem`    | Optional: `vocals`, `drums`, `bass`, or `other` |

## Tests

```bash
pytest
```
