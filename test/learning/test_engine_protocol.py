"""Tests for the versioned, host-neutral local engine transport."""

import json
import subprocess
import sys

import pytest

from learning.engine_protocol import handle_request


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


def test_protocol_reviews_binary_value_masks_without_persisting_pixels():
    mask = [int(2 <= x < 6 and 2 <= y < 6) for y in range(8) for x in range(8)]
    response = handle_request(
        {
            "protocol_version": 1,
            "request_id": "value-1",
            "operation": "review_value_masks",
            "payload": {
                "front_mask": mask,
                "turned_mask": mask,
                "width": 8,
                "height": 8,
                "light_direction": "top_left",
                "boundary_hardness": "hard",
            },
        }
    )
    assert response["result"]["measurements"]["front_turned_consistency"] == 1
    assert "front_mask" not in response["result"]


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


def test_protocol_records_project_local_advice_feedback(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    handle_request(
        {
            "protocol_version": 1,
            "request_id": "create-1",
            "operation": "create_exercise_project",
            "payload": {
                "directory": str(tmp_path),
                "title": "Anime head practice",
                "attempt_id": "attempt-1",
            },
        }
    )
    review = handle_request(_request())["result"]
    handle_request(
        {
            "protocol_version": 1,
            "request_id": "store-review",
            "operation": "record_attempt_review",
            "payload": {
                "directory": str(tmp_path),
                "attempt_id": "attempt-1",
                "review": review,
            },
        }
    )

    response = handle_request(
        {
            "protocol_version": 1,
            "request_id": "feedback-1",
            "operation": "record_advice_feedback",
            "payload": {
                "directory": str(tmp_path),
                "attempt_id": "attempt-1",
                "review_id": review["id"],
                "rating": "helpful",
                "note": "The construction-axis explanation helped.",
            },
        }
    )

    assert response["result"]["changed"] is True


def test_completed_front_attempt_recommends_orientation_without_locking(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    handle_request(
        {
            "protocol_version": 1,
            "request_id": "create-1",
            "operation": "create_exercise_project",
            "payload": {
                "directory": str(tmp_path),
                "title": "Anime head practice",
                "attempt_id": "attempt-1",
            },
        }
    )
    before = handle_request(
        {
            "protocol_version": 1,
            "request_id": "progress-1",
            "operation": "project_progress_snapshot",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert before["result"]["recommended_exercise_id"] == "anime-head-front-construction"

    handle_request(
        {
            "protocol_version": 1,
            "request_id": "complete-1",
            "operation": "set_attempt_completion",
            "payload": {
                "directory": str(tmp_path),
                "attempt_id": "attempt-1",
                "completed": True,
            },
        }
    )
    after = handle_request(
        {
            "protocol_version": 1,
            "request_id": "progress-2",
            "operation": "project_progress_snapshot",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert after["result"]["recommended_exercise_id"] == "anime-head-orientation"


def test_protocol_reviews_one_selected_three_quarter_head():
    response = handle_request(
        {
            "protocol_version": 1,
            "request_id": "orientation-review-1",
            "operation": "review_orientation_head",
            "payload": {
                "view": "right_three_quarter",
                "landmarks": {
                    "cranium_center": [0.5, 0.38],
                    "cranium_radius": 0.25,
                    "centerline_top": [0.575, 0.15],
                    "chin": [0.575, 0.82],
                    "eye_line_left": [0.3, 0.4],
                    "eye_line_right": [0.7, 0.4],
                    "left_contour": [0.3, 0.4],
                    "right_contour": [0.7, 0.4],
                    "jaw_left": [0.36, 0.64],
                    "jaw_right": [0.65, 0.63],
                },
            },
        }
    )
    assert response["result"]["exercise_id"] == "anime-head-orientation"
    assert response["result"]["rubric_id"] == "anime-head-orientation-structure"


def test_protocol_reviews_front_and_turned_design_pair():
    response = handle_request(
        {
            "protocol_version": 1,
            "request_id": "pair-review-1",
            "operation": "review_cranial_jaw_pair",
            "payload": {
                "variant_id": "neutral",
                "front_landmarks": {
                    "cranium_center": [0.5, 0.35],
                    "cranium_radius": 0.25,
                    "centerline_top": [0.5, 0.1],
                    "centerline_bottom": [0.5, 0.6],
                    "eye_line_left": [0.3, 0.4],
                    "eye_line_right": [0.7, 0.4],
                    "jaw_left": [0.36, 0.65],
                    "jaw_right": [0.64, 0.65],
                    "chin": [0.5, 0.82],
                },
                "turned_landmarks": {
                    "cranium_center": [0.5, 0.35],
                    "cranium_radius": 0.25,
                    "centerline_top": [0.56, 0.1],
                    "chin": [0.56, 0.82],
                    "eye_line_left": [0.3, 0.4],
                    "eye_line_right": [0.7, 0.4],
                    "left_contour": [0.38, 0.4],
                    "right_contour": [0.7, 0.4],
                    "jaw_left": [0.4, 0.65],
                    "jaw_right": [0.62, 0.65],
                },
            },
        }
    )
    assert response["result"]["exercise_id"] == "anime-head-volume-jaw"
    assert response["result"]["rubric_id"] == "anime-head-volume-jaw-pair"


def test_protocol_reviews_selected_eye_study():
    landmarks = {
        "centerline_top": [0.5, 0.1],
        "chin": [0.5, 0.9],
        "eye_line_left": [0.15, 0.4],
        "eye_line_right": [0.85, 0.4],
        "left_inner": [0.42, 0.4],
        "left_outer": [0.2, 0.4],
        "right_inner": [0.58, 0.4],
        "right_outer": [0.8, 0.4],
        "left_upper_peak": [0.31, 0.34],
        "left_lower_peak": [0.31, 0.46],
        "right_upper_peak": [0.69, 0.34],
        "right_lower_peak": [0.69, 0.46],
        "left_iris_top": [0.31, 0.35],
        "left_iris_bottom": [0.31, 0.45],
        "right_iris_top": [0.69, 0.35],
        "right_iris_bottom": [0.69, 0.45],
    }
    response = handle_request(
        {
            "protocol_version": 1,
            "request_id": "eye-review-1",
            "operation": "review_eye_pair",
            "payload": {"view": "front", "stage": "style_expression", "landmarks": landmarks},
        }
    )
    assert response["result"]["exercise_id"] == "anime-head-eyes"
    assert response["result"]["rubric_id"] == "anime-head-eyes-style_expression"
    assert "expression_consistency" in response["result"]["measurements"]


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
        [sys.executable, "-m", "learning.engine_protocol"],
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
        [sys.executable, "-m", "learning.engine_protocol"],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "invalid_request"
    assert completed.stderr == ""
