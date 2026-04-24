# yt-split

Local pipeline: download audio from a YouTube URL with **yt-dlp**, separate stems with **Demucs** (`htdemucs`). See [CLAUDE.md](./CLAUDE.md) for project rules and hardware checks.

## Requirements

- Python 3.10+
- **static-ffmpeg** (declared in `requirements.txt`) supplies ffmpeg/ffprobe for yt-dlp and Demucs when your system does not. The first `--url` run may download those binaries. If `ffmpeg` is already on your `PATH`, that copy is used instead.

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

| Flag | Description |
|------|-------------|
| `--check` | Print CUDA, RAM, and warnings; no download |
| `--url URL` | YouTube URL to process |
| `--stem` | Optional: `vocals`, `drums`, `bass`, or `other` |

## Tests

```bash
pytest
```
