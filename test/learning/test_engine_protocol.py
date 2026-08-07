"""Tests for the versioned, host-neutral local engine transport."""

import json
import subprocess
import sys

import pytest

from cel_shaded_generator.learning.engine_protocol import handle_request


def _request():
    return {
        "protocol_version": 1,
        "request_id": "attempt-1",
        "operation": "review_front_head",
        "payload": {
            "landmarks": {
                "cranium_center": [0.5, 0.4],
                "cranium_radius": 0.25,
                "centerline_top": [0.5, 0.15],
                "centerline_bottom": [0.5, 0.85],
                "eye_line_left": [0.3, 0.4],
                "eye_line_right": [0.7, 0.4],
                "jaw_left": [0.34, 0.65],
                "jaw_right": [0.66, 0.65],
                "chin": [0.5, 0.85],
            }
        },
    }


def test_protocol_returns_versioned_review():
    response = handle_request(_request())
    assert response["ok"] is True
    assert response["request_id"] == "attempt-1"
    assert response["result"]["method_id"] == "anime-head-construction-v1"
    assert response["result"]["rubric_version"] == "1.0.0"


def test_protocol_creates_portable_exercise_project(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    request = {
        "protocol_version": 1,
        "request_id": "create-1",
        "operation": "create_exercise_project",
        "payload": {
            "directory": str(tmp_path),
            "title": "Anime head practice",
            "document_asset": "artwork/attempt-001.kra",
            "attempt_id": "attempt-1",
        },
    }
    response = handle_request(request)
    assert response["ok"]
    assert response["result"]["attempt_id"] == "attempt-1"
    assert (tmp_path / "project.json").is_file()


@pytest.mark.parametrize(
    "change",
    [
        {"protocol_version": 2},
        {"request_id": ""},
        {"operation": "run_arbitrary_code"},
        {"payload": {}},
    ],
)
def test_protocol_rejects_unknown_or_incomplete_requests(change):
    with pytest.raises(ValueError):
        handle_request(_request() | change)


def test_module_cli_reads_and_writes_one_json_message():
    completed = subprocess.run(
        [sys.executable, "-m", "cel_shaded_generator.learning.engine_protocol"],
        input=json.dumps(_request()),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["ok"] is True
    assert response["result"]["id"] == "attempt-1"


def test_module_cli_returns_structured_error_without_traceback():
    completed = subprocess.run(
        [sys.executable, "-m", "cel_shaded_generator.learning.engine_protocol"],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "invalid_request"
    assert completed.stderr == ""
