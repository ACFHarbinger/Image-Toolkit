"""Unit tests for the Scan & Tag service layer and handlers (L-04 / #898)."""

from __future__ import annotations

from pathlib import Path

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.scan import (
    MetadataItemCommand,
    SaveMetadataCommand,
    ScanDirectoryCommand,
    ScanService,
    ScanServiceProtocol,
    SuggestTagsCommand,
)
from middleware.src.sidecar.handlers.scan import (
    handle_save_metadata,
    handle_scan_directory,
    handle_suggest_tags,
)
from PIL import Image


def _make_image(path: Path, size: tuple[int, int] = (32, 32)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=(100, 150, 200))
    img.save(path)
    return path


def test_scan_service_protocol_conformance():
    service = ScanService()
    assert isinstance(service, ScanServiceProtocol)


def test_scan_directory_empty_or_nonexistent(tmp_path: Path):
    service = ScanService()
    missing_dir = tmp_path / "nonexistent"
    with pytest.raises(CommandValidationError):
        service.scan_directory(ScanDirectoryCommand(directory=str(missing_dir)))


def test_scan_directory_discovers_images(tmp_path: Path):
    _make_image(tmp_path / "folder_a" / "img1.png", (64, 48))
    _make_image(tmp_path / "folder_a" / "sub" / "img2.jpg", (100, 100))
    txt = tmp_path / "folder_a" / "note.txt"
    txt.write_text("not an image")

    service = ScanService()

    # Flat scan
    res_flat = service.scan_directory(
        ScanDirectoryCommand(directory=str(tmp_path / "folder_a"), recursive=False)
    )
    assert res_flat.total_found == 1
    assert res_flat.images[0].filename == "img1.png"
    assert res_flat.images[0].width == 64
    assert res_flat.images[0].height == 48
    assert res_flat.database_available is False
    assert res_flat.images[0].in_database is False

    # Recursive scan
    res_rec = service.scan_directory(
        ScanDirectoryCommand(directory=str(tmp_path / "folder_a"), recursive=True)
    )
    assert res_rec.total_found == 2
    filenames = {img.filename for img in res_rec.images}
    assert filenames == {"img1.png", "img2.jpg"}


def test_suggest_tags_heuristics(tmp_path: Path):
    service = ScanService()
    p1 = str(tmp_path / "Anime_Wallpapers" / "Cyberpunk" / "neon_city_01.png")
    p2 = str(tmp_path / "Portraits" / "character_hero.jpg")

    result = service.suggest_tags(SuggestTagsCommand(paths=(p1, p2)))
    assert p1 in result.suggestions
    assert p2 in result.suggestions

    tags_p1 = result.suggestions[p1]
    assert "cyberpunk" in tags_p1
    assert "neon" in tags_p1
    assert "city" in tags_p1

    tags_p2 = result.suggestions[p2]
    assert "portraits" in tags_p2
    assert "character" in tags_p2
    assert "hero" in tags_p2


def test_save_metadata_counts_only_completed_writes(tmp_path: Path, monkeypatch):
    written: list[str] = []

    class _Repo:
        def __init__(self, session) -> None:
            assert session == "session"

        def add_image(self, file_path, group_name=None, subgroup_name=None, tags=None, **_kwargs):
            if file_path.endswith("bad.png"):
                raise RuntimeError("write failed")
            written.append(file_path)
            assert tags == ["art"]
            assert group_name == "people"
            return 7

    monkeypatch.setattr("middleware.src.database.unified.image_repo.ImageRepo", _Repo)
    service = ScanService(db_session="session")
    result = service.save_metadata(
        SaveMetadataCommand(
            items=(
                MetadataItemCommand(path=str(tmp_path / "ok.png"), tags=("art",), group_name="people"),
                MetadataItemCommand(path=str(tmp_path / "bad.png"), tags=("art",), group_name="people"),
            )
        )
    )
    assert written == [str(tmp_path / "ok.png")]
    assert result.database_available is True
    assert result.saved_count == 1
    assert result.success is False
    assert any("bad.png" in error for error in result.errors)


def test_save_metadata_without_db_session(tmp_path: Path):
    service = ScanService()
    cmd = SaveMetadataCommand(
        items=(
            MetadataItemCommand(path=str(tmp_path / "test.png"), tags=("test", "art")),
        )
    )
    res = service.save_metadata(cmd)
    assert res.database_available is False
    assert res.success is False
    assert res.saved_count == 0
    assert len(res.errors) > 0


def test_sidecar_handlers_dispatch(tmp_path: Path):
    img = _make_image(tmp_path / "test.webp")
    scan_res = handle_scan_directory(None, {"directory": str(tmp_path), "recursive": False})
    assert scan_res["total_found"] == 1
    assert scan_res["images"][0]["filename"] == "test.webp"

    suggest_res = handle_suggest_tags(None, {"paths": [str(img)]})
    assert str(img) in suggest_res["suggestions"]

    save_res = handle_save_metadata(None, {"items": [{"path": str(img), "tags": ["tag1"]}]})
    assert save_res["database_available"] is False
    assert save_res["success"] is False
