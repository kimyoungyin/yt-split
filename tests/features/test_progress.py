import io
import json

from src.features.progress import ProgressEmitter


def test_emitter_disabled_writes_nothing():
    buf = io.StringIO()
    emitter = ProgressEmitter(enabled=False, stream=buf)
    emitter.emit("progress", stage="download", value=0.5)
    assert buf.getvalue() == ""


def test_emitter_enabled_writes_one_json_line_per_event():
    buf = io.StringIO()
    emitter = ProgressEmitter(enabled=True, stream=buf)
    emitter.emit("stage", stage="download", status="start")
    emitter.emit("progress", stage="download", value=0.4)
    emitter.emit("stage", stage="download", status="done")

    lines = buf.getvalue().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert parsed[0] == {"type": "stage", "stage": "download", "status": "start"}
    assert parsed[1]["type"] == "progress"
    assert parsed[1]["value"] == 0.4
    assert parsed[2]["status"] == "done"


def test_emitter_preserves_unicode_in_payload():
    buf = io.StringIO()
    emitter = ProgressEmitter(enabled=True, stream=buf)
    emitter.emit("error", message="다운로드 실패: 한글")
    payload = json.loads(buf.getvalue().strip())
    assert payload["message"] == "다운로드 실패: 한글"
