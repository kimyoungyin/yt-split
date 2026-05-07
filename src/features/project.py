"""Project metadata: creation, atomic write, listing."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def create_project_metadata(
    base: Path,
    *,
    project_id: str,
    title: str,
    url: str,
    device: str,
    stem_mode: str,
    tracks: dict[str, Path],
) -> Path:
    """Write v1 schema metadata to <base>/projects/<project_id>.json.

    tracks values are absolute paths; stored as posix relative paths from
    <base>/projects/<project_id>/ so the library remains portable if base moves.
    Raises ValueError if any track path escapes the project directory.
    Write is atomic via .tmp → rename.
    """
    project_dir = base / "projects" / project_id
    meta_path = base / "projects" / f"{project_id}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    rel_tracks: dict[str, str] = {}
    for stem_name, abs_path in tracks.items():
        try:
            rel = abs_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            raise ValueError(
                f"트랙 경로가 프로젝트 디렉터리 밖에 있습니다: {abs_path}"
            )
        if ".." in rel.parts:
            raise ValueError(f"경로 탈출 감지: {rel}")
        rel_tracks[stem_name] = rel.as_posix()

    data: dict[str, Any] = {
        "schema_version": 1,
        "id": project_id,
        "title": title,
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "device": device,
        "stem_mode": stem_mode,
        "tracks": rel_tracks,
    }

    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.rename(meta_path)
    return meta_path


def list_projects(base: Path) -> list[dict[str, Any]]:
    """Scan <base>/projects/*.json and return v1 metadata dicts sorted by created_at desc."""
    projects_dir = base / "projects"
    if not projects_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for json_file in projects_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if data.get("schema_version") == 1:
                results.append(data)
        except Exception:
            pass
    results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return results
