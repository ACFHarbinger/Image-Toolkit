"""Fixture management only: never executes the benchmark or generates a corpus."""
import json
from pathlib import Path

import pytest

from backend.benchmark import bench_dataset_analyzer as bench


def test_refuses_regeneration_outside_test_root(tmp_path):
    with pytest.raises(ValueError, match="child"):
        bench._setup(Path("/"), 1200, True)


def test_refuses_unmarked_directory(tmp_path):
    important = tmp_path / "keep.txt"
    important.write_text("user data")
    with pytest.raises(ValueError, match="non-fixture"):
        bench._setup(tmp_path, 1200, True)
    assert important.read_text() == "user data"


def test_refuses_unknown_files_even_with_marker(tmp_path):
    (tmp_path / bench._FIXTURE_MARKER).write_text(json.dumps(
        {"version": 2, "count": 1200, "files": ["img_0000.jpg"]}))
    (tmp_path / "img_0000.jpg").write_bytes(b"fixture")
    important = tmp_path / "notes.txt"
    important.write_text("keep")
    with pytest.raises(ValueError, match="unrecognized"):
        bench._setup(tmp_path, 1200, True)
    assert important.is_file()


def test_legacy_marker_does_not_authorize_deletion(tmp_path):
    (tmp_path / bench._FIXTURE_MARKER).write_text(json.dumps({"version": 1, "count": 1200}))
    with pytest.raises(ValueError, match="Legacy"):
        bench._setup(tmp_path, 1200, True)


def test_count_leaves_enough_images_for_twenty_duplicates(tmp_path):
    with pytest.raises(ValueError, match="20 normal"):
        bench._setup(tmp_path, 70, False)
