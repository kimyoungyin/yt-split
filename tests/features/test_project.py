"""Tests for src/features/project.py — metadata creation and listing."""
import json
from pathlib import Path


def test_create_project_metadata_writes_v1_schema(tmp_path):
    """메타 파일이 v1 스키마 + 상대 경로로 저장되어야 한다."""
    from src.features.project import create_project_metadata

    tracks = {
        "vocals": tmp_path / "projects" / "abc" / "stems" / "vocals.wav",
        "drums":  tmp_path / "projects" / "abc" / "stems" / "drums.wav",
    }
    for p in tracks.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    meta_path = create_project_metadata(
        base=tmp_path,
        project_id="abc",
        title="Test Song",
        url="https://youtu.be/x",
        device="cpu",
        stem_mode="all",
        tracks=tracks,
    )

    data = json.loads(meta_path.read_text())
    assert data["schema_version"] == 1
    assert data["id"] == "abc"
    assert data["title"] == "Test Song"
    assert data["device"] == "cpu"
    assert data["tracks"]["vocals"] == "stems/vocals.wav"
    assert data["tracks"]["drums"] == "stems/drums.wav"


def test_create_project_metadata_is_atomic(tmp_path):
    """정상 완료 후 .tmp 파일은 남지 않아야 한다."""
    from src.features.project import create_project_metadata

    stems_dir = tmp_path / "projects" / "xyz" / "stems"
    stems_dir.mkdir(parents=True)
    wav = stems_dir / "vocals.wav"
    wav.touch()

    meta_path = create_project_metadata(
        base=tmp_path,
        project_id="xyz",
        title="Atomic Song",
        url="https://youtu.be/y",
        device="cpu",
        stem_mode="all",
        tracks={"vocals": wav},
    )

    assert meta_path.exists()
    assert not meta_path.with_suffix(".json.tmp").exists()


def test_create_project_metadata_blocks_path_traversal(tmp_path):
    """tracks 경로에 .. 가 포함되면 ValueError를 던져야 한다."""
    import pytest
    from src.features.project import create_project_metadata

    evil_path = (tmp_path / "projects" / "evil" / ".." / ".." / "secret.wav").resolve()

    with pytest.raises((ValueError, Exception)):
        create_project_metadata(
            base=tmp_path,
            project_id="evil",
            title="Evil",
            url="https://youtu.be/z",
            device="cpu",
            stem_mode="all",
            tracks={"vocals": evil_path},
        )


def test_list_projects_returns_sorted_by_created_at_desc(tmp_path):
    """list_projects는 created_at 역순으로 정렬된 list를 반환해야 한다."""
    from src.features.project import create_project_metadata, list_projects

    for pid, title, ts in [
        ("p1", "Old Song", "2026-01-01T00:00:00+00:00"),
        ("p2", "New Song", "2026-06-01T00:00:00+00:00"),
    ]:
        stems_dir = tmp_path / "projects" / pid / "stems"
        stems_dir.mkdir(parents=True)
        wav = stems_dir / "vocals.wav"
        wav.touch()
        meta = create_project_metadata(
            base=tmp_path,
            project_id=pid,
            title=title,
            url="https://youtu.be/x",
            device="cpu",
            stem_mode="all",
            tracks={"vocals": wav},
        )
        # Override created_at for deterministic test
        data = json.loads(meta.read_text())
        data["created_at"] = ts
        meta.write_text(json.dumps(data))

    results = list_projects(tmp_path)
    assert len(results) == 2
    assert results[0]["id"] == "p2"
    assert results[1]["id"] == "p1"


def test_list_projects_returns_empty_when_no_dir(tmp_path):
    """projects/ 디렉터리가 없으면 빈 리스트를 반환해야 한다."""
    from src.features.project import list_projects

    assert list_projects(tmp_path) == []
