"""NDJSON progress emitter for sidecar mode.

When the CLI is invoked with --sidecar, every user-visible message must be
serialized as a single-line JSON object on stdout so the Tauri host can parse
events line by line. In normal CLI mode the emitter is a no-op and existing
print() calls keep the human-readable behavior.

The emitter writes to sys.__stdout__ (the original stdout the process was
started with) rather than sys.stdout. That way contextlib.redirect_stdout
blocks — used elsewhere to silence demucs/yt-dlp human prints — cannot
accidentally divert NDJSON events into the log channel.
"""
import json
import sys
from typing import Any, Optional, TextIO


class ProgressEmitter:
    """Writes one JSON object per line to a configurable stream.

    Use `emit(type, **fields)` for events. In sidecar mode `enabled=True` and
    the stream defaults to sys.__stdout__ so it survives stdout redirection.
    Pass an explicit `stream` (e.g. an io.StringIO) for unit tests.
    """

    def __init__(self, enabled: bool = False, stream: Optional[TextIO] = None) -> None:
        self.enabled = enabled
        self._stream: TextIO = stream if stream is not None else (sys.__stdout__ or sys.stdout)

    def emit(self, type: str, **fields: Any) -> None:
        if not self.enabled:
            return
        payload = {"type": type, **fields}
        self._stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._stream.flush()
