"""Unit tests for the no-Qt Cloud Run extraction command builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def worker_module():
    path = Path(__file__).parents[3] / "infra/cloud/gcd/worker/extraction.py"
    spec = importlib.util.spec_from_file_location("gcd_extraction", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_job_validation_requires_bounded_gcs_range(worker_module):
    with pytest.raises(ValueError, match="gs://"):
        worker_module.ExtractionJob.from_json({"source_uri": "https://example/video"})
    with pytest.raises(ValueError, match="greater"):
        worker_module.ExtractionJob.from_json(
            {"source_uri": "gs://bucket/video.mp4", "start_ms": 5, "end_ms": 5}
        )


@pytest.mark.parametrize("mode, expected", [("range", "frame_%06d.png"), ("gif", "clip.gif"), ("video", "clip.mp4")])
def test_commands_are_bounded_and_write_expected_output(worker_module, tmp_path, mode, expected):
    job = worker_module.ExtractionJob.from_json(
        {
            "job_id": "safe/id",
            "source_uri": "gs://source/input.mp4",
            "mode": mode,
            "start_ms": 1000,
            "end_ms": 3000,
            "fps": 24,
            "target_size": [640, 360],
        }
    )
    commands = worker_module.build_commands(job, tmp_path / "source", tmp_path)

    assert all("-t" in command and "-threads" in command for command in commands)
    assert expected in commands[-1][-1]
    if mode == "gif":
        assert len(commands) == 2
        assert "palettegen" in " ".join(commands[0])
        assert "paletteuse" in " ".join(commands[1])
