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
                "front_form_mask": mask,
                "front_cast_mask": [0] * 64,
                "turned_form_mask": mask,
                "turned_cast_mask": [0] * 64,
                "width": 8,
                "height": 8,
                "light_direction": "top_left",
                "boundary_hardness": "hard",
            },
        }
    )
    assert response["result"]["measurements"]["front_turned_consistency"] == 1
    assert "front_form_mask" not in response["result"]


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


def test_protocol_adds_and_advances_chapter_pages(tmp_path):
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
                "title": "Chapter",
                "document_asset": "artwork/attempt-001.kra",
                "attempt_id": "attempt-1",
            },
        }
    )
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "01.kra").write_bytes(b"page one")

    add = handle_request(
        {
            "protocol_version": 1,
            "request_id": "add-1",
            "operation": "add_chapter_page",
            "payload": {
                "directory": str(tmp_path),
                "document_asset": "pages/01.kra",
                "panel_id": "panel-1",
            },
        }
    )
    assert add["ok"]
    page_id = add["result"]["page_id"]

    queued = handle_request(
        {
            "protocol_version": 1,
            "request_id": "next-1",
            "operation": "next_pending_chapter_page",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert queued["result"]["page_id"] == page_id
    assert queued["result"]["status"] == "pending"

    status = handle_request(
        {
            "protocol_version": 1,
            "request_id": "status-1",
            "operation": "set_chapter_page_status",
            "payload": {
                "directory": str(tmp_path),
                "page_id": page_id,
                "status": "accepted",
            },
        }
    )
    assert status["result"]["changed"] is True

    empty_queue = handle_request(
        {
            "protocol_version": 1,
            "request_id": "next-2",
            "operation": "next_pending_chapter_page",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert empty_queue["result"] == {"page_id": None}

    snapshot = handle_request(
        {
            "protocol_version": 1,
            "request_id": "snapshot-1",
            "operation": "project_progress_snapshot",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert snapshot["result"]["chapter"]["pages"][0]["status"] == "accepted"
    assert snapshot["result"]["chapter"]["next_pending_page_id"] is None


def test_protocol_configures_study_consent_and_records_a_session(tmp_path):
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
                "title": "Study",
                "document_asset": "artwork/attempt-001.kra",
                "attempt_id": "attempt-1",
            },
        }
    )
    consent = handle_request(
        {
            "protocol_version": 1,
            "request_id": "consent-1",
            "operation": "configure_study_consent",
            "payload": {"directory": str(tmp_path), "opted_in": True},
        }
    )
    assert consent["result"]["changed"] is True

    session = handle_request(
        {
            "protocol_version": 1,
            "request_id": "session-1",
            "operation": "record_study_session",
            "payload": {
                "directory": str(tmp_path),
                "baseline_attempt_id": "attempt-1",
                "explanation_rating": "helpful",
                "completed": True,
            },
        }
    )
    assert session["ok"]
    assert session["result"]["session_id"]

    snapshot = handle_request(
        {
            "protocol_version": 1,
            "request_id": "snapshot-1",
            "operation": "project_progress_snapshot",
            "payload": {"directory": str(tmp_path)},
        }
    )
    assert snapshot["result"]["study"]["consent"]["opted_in"] is True
    assert snapshot["result"]["study"]["sessions"][0]["explanation_rating"] == "helpful"


def test_protocol_authors_binds_and_propagates_correspondence(tmp_path):
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
                "title": "Color project",
                "document_asset": "artwork/attempt-001.kra",
                "attempt_id": "attempt-1",
            },
        }
    )
    upsert = handle_request(
        {
            "protocol_version": 1,
            "request_id": "upsert-1",
            "operation": "upsert_project_correspondence_set",
            "payload": {
                "directory": str(tmp_path),
                "correspondence_set": {
                    "id": "aiko-page-1",
                    "style_bible_id": "aiko-tv",
                    "correspondences": [
                        {"id": "r1", "region_id": "hair-front-large", "material_id": "hair"}
                    ],
                    "recovery_revisions": 10,
                    "schema_version": 1,
                },
            },
        }
    )
    assert upsert["ok"]
    asset_path = upsert["result"]["asset_path"]

    read = handle_request(
        {
            "protocol_version": 1,
            "request_id": "read-1",
            "operation": "project_correspondence_set_payload",
            "payload": {"directory": str(tmp_path), "asset_path": asset_path},
        }
    )
    assert read["result"]["id"] == "aiko-page-1"

    propagate = handle_request(
        {
            "protocol_version": 1,
            "request_id": "propagate-1",
            "operation": "propagate_project_correspondence",
            "payload": {
                "directory": str(tmp_path),
                "asset_path": asset_path,
                "source_id": "r1",
                "target_region_ids": ["hair-back-large"],
            },
        }
    )
    assert {item["region_id"] for item in propagate["result"]["correspondences"]} == {
        "hair-front-large",
        "hair-back-large",
    }

    detach = handle_request(
        {
            "protocol_version": 1,
            "request_id": "detach-1",
            "operation": "detach_correspondence_set",
            "payload": {"directory": str(tmp_path), "asset_path": asset_path},
        }
    )
    assert detach["result"]["changed"] is True

    attach = handle_request(
        {
            "protocol_version": 1,
            "request_id": "attach-1",
            "operation": "attach_correspondence_set",
            "payload": {"directory": str(tmp_path), "asset_path": asset_path},
        }
    )
    assert attach["result"]["changed"] is True


def test_protocol_ranks_candidates_and_learns_from_the_artists_choice(tmp_path):
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
                "title": "Color project",
                "document_asset": "artwork/attempt-001.kra",
                "attempt_id": "attempt-1",
            },
        }
    )
    reference = tmp_path / "references/front.png"
    reference.parent.mkdir()
    reference.write_bytes(b"reference")
    upsert = handle_request(
        {
            "protocol_version": 1,
            "request_id": "upsert-bible-1",
            "operation": "upsert_project_style_bible",
            "payload": {
                "directory": str(tmp_path),
                "style_bible": {
                    "id": "aiko",
                    "character_name": "Aiko",
                    "style_name": "TV cel",
                    "materials": [
                        {
                            "id": "hair",
                            "label": "Hair",
                            "palette": {
                                "local": "#332233",
                                "light": "#665566",
                                "shadow": "#110F18",
                            },
                        },
                        {
                            "id": "skin",
                            "label": "Skin",
                            "palette": {
                                "local": "#EEDDCC",
                                "light": "#FFEEDD",
                                "shadow": "#AA8866",
                            },
                        },
                    ],
                    "reference_views": [
                        {"id": "front", "label": "Front", "asset_path": "references/front.png"}
                    ],
                    "schema_version": 2,
                },
            },
        }
    )
    assert upsert["ok"]
    bible_asset_path = upsert["result"]["asset_path"]

    rank = handle_request(
        {
            "protocol_version": 1,
            "request_id": "rank-1",
            "operation": "rank_correspondence_materials",
            "payload": {
                "directory": str(tmp_path),
                "bible_asset_path": bible_asset_path,
                "region_id": "hair-front-large",
                "adjacency_agreements": {"hair": 0.1, "skin": 0.9},
            },
        }
    )
    assert rank["ok"]
    candidates = rank["result"]["candidates"]
    assert {item["material_id"] for item in candidates} == {"hair", "skin"}

    choice = handle_request(
        {
            "protocol_version": 1,
            "request_id": "choice-1",
            "operation": "record_correspondence_choice",
            "payload": {
                "directory": str(tmp_path),
                "chosen_material_id": "hair",
                "candidates": candidates,
            },
        }
    )
    assert choice["ok"]
    assert choice["result"]["update_count"] == 1
    assert choice["result"]["name_weight"] > choice["result"]["adjacency_weight"]


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
