"""Fixture management only: never executes the benchmark or generates a corpus."""
import json
from pathlib import Path

import pytest

from backend.benchmark import bench_dataset_analyzer as bench


@pytest.fixture
def fixture_dir(tmp_path, monkeypatch):
    """A child of a fake ~/Downloads/Data/Tests, so the root guard passes."""
    monkeypatch.setattr(bench.Path, "home", classmethod(lambda cls: tmp_path))
    child = tmp_path / "Downloads" / "Data" / "Tests" / "bench"
    child.mkdir(parents=True)
    return child


def test_refuses_regeneration_outside_test_root(tmp_path):
    with pytest.raises(ValueError, match="child"):
        bench._setup(Path("/"), 1200, True)


def test_refuses_unmarked_directory(fixture_dir):
    important = fixture_dir / "keep.txt"
    important.write_text("user data")
    with pytest.raises(ValueError, match="non-fixture"):
        bench._setup(fixture_dir, 1200, True)
    assert important.read_text() == "user data"


def test_refuses_unknown_files_even_with_marker(fixture_dir):
    (fixture_dir / bench._FIXTURE_MARKER).write_text(json.dumps(
        {"version": 2, "count": 1200, "files": ["img_0000.jpg"]}))
    (fixture_dir / "img_0000.jpg").write_bytes(b"fixture")
    important = fixture_dir / "notes.txt"
    important.write_text("keep")
    with pytest.raises(ValueError, match="unrecognized"):
        bench._setup(fixture_dir, 1200, True)
    assert important.is_file()


def test_legacy_marker_does_not_authorize_deletion(fixture_dir):
    (fixture_dir / bench._FIXTURE_MARKER).write_text(json.dumps({"version": 1, "count": 1200}))
    with pytest.raises(ValueError, match="Legacy"):
        bench._setup(fixture_dir, 1200, True)


def test_count_leaves_enough_images_for_twenty_duplicates(fixture_dir):
    with pytest.raises(ValueError, match="20 normal"):
        bench._setup(fixture_dir, 70, False)


def test_native_floor_bounds_saving_on_tiny_fixture(fixture_dir, monkeypatch):
    image = fixture_dir / "img_0000.png"
    from PIL import Image
    Image.new("RGB", (8, 8)).save(image)
    image.with_suffix(".txt").write_text("ohwx, solo")
    monkeypatch.setattr(bench, "_ALL_PATHS", [str(image)])
    bench._evict_page_cache()
    floor = bench._native_floor()
    assert floor["floor_sec"] == floor["read_sec"] + floor["sha256_sec"]
    assert floor["max_native_saving_sec"] >= 0.0
