"""CloudJob — canonical job model + wire-schema builder (pure logic)."""

from __future__ import annotations

import pytest
from backend.src.web.cloud.compute import CloudJob


def test_to_job_json_matches_worker_schema():
    job = CloudJob(
        source_uri="gs://bucket/in.mp4",
        mode="gif",
        start_ms=1000,
        end_ms=3000,
        fps=24,
        target_size=(640, 360),
        job_id="job-abc",
    )
    payload = job.to_job_json()
    assert payload == {
        "job_id": "job-abc",
        "source_uri": "gs://bucket/in.mp4",
        "mode": "gif",
        "start_ms": 1000,
        "end_ms": 3000,
        "fps": 24,
        "output_prefix": "cloud-jobs/job-abc",
        "task": "extract",
        "target_size": [640, 360],
    }

    # ...and the worker's own parser accepts that exact payload.
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).parents[3] / "infra/cloud/gcd/worker/extraction.py"
    spec = importlib.util.spec_from_file_location("gcd_extraction_roundtrip", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    ejob = mod.ExtractionJob.from_json(payload)
    assert ejob.mode == "gif" and ejob.start_ms == 1000 and ejob.end_ms == 3000
    assert ejob.target_size == (640, 360)


def test_validation_mirrors_worker():
    with pytest.raises(ValueError, match="end_ms"):
        CloudJob(source_uri="gs://b/o", start_ms=5, end_ms=5)
    with pytest.raises(ValueError, match="mode"):
        CloudJob(source_uri="gs://b/o", mode="thumbnail", start_ms=0, end_ms=1)
    with pytest.raises(ValueError, match="source_uri"):
        CloudJob(source_uri="", start_ms=0, end_ms=1)


def test_fps_clamped_and_job_id_slugged():
    job = CloudJob(source_uri="gs://b/o", start_ms=0, end_ms=1000, fps=999, job_id="a b/c!")
    assert job.fps == 120
    assert job.job_id == "a_b_c_"
    assert job.output_prefix == "cloud-jobs/a_b_c_"


def test_from_extraction_config_maps_single_and_open_ended():
    # "single" -> range with a one-frame window
    single = CloudJob.from_extraction_config(
        {"type": "single", "start_ms": 2000, "end_ms": 2000, "fps": 25},
        source_uri="gs://b/o",
    )
    assert single.mode == "range"
    assert single.end_ms == 2000 + 40  # 1000/25

    # open-ended (-1) gif also gets a bounded window
    gif = CloudJob.from_extraction_config(
        {"type": "gif", "start_ms": 0, "end_ms": -1, "fps": 20,
         "target_resolution": (320, 240)},
        source_uri="gs://b/o",
    )
    assert gif.mode == "gif"
    assert gif.end_ms == 50
    assert gif.target_size == (320, 240)


def test_from_extraction_config_passes_range_through():
    job = CloudJob.from_extraction_config(
        {"type": "range", "start_ms": 1000, "end_ms": 5000, "fps": 30},
        source_uri="gs://b/o.mp4",
        job_id="run-1",
    )
    assert (job.mode, job.start_ms, job.end_ms, job.fps) == ("range", 1000, 5000, 30)


def test_from_ui_payload_parses_resolution_string():
    job = CloudJob.from_ui_payload(
        {"job_id": "job-9", "task_type": "GIF Extraction", "resolution": "1280x720",
         "start_ms": 100, "end_ms": 900, "fps": 24},
        source_uri="gs://b/o",
    )
    assert job.mode == "gif"
    assert job.target_size == (1280, 720)
    assert job.job_id == "job-9"
