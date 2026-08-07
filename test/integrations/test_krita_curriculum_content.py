"""Validation for fully authored offline curriculum content."""

import json
from pathlib import Path

CONTENT = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/content"


def test_head_orientation_lesson_is_complete_and_versioned():
    lesson = json.loads((CONTENT / "head_orientation.json").read_text(encoding="utf-8"))

    assert lesson["id"] == "anime-head-orientation"
    assert lesson["version"] == "1.0.0"
    assert lesson["method_id"] == "anime-head-construction-v1"
    assert lesson["prerequisite_ids"] == ["anime-head-front-construction"]
    assert len(lesson["learning_objectives"]) >= 5
    assert len(lesson["theory"]) >= 4
    assert len(lesson["steps"]) >= 7
    assert len(lesson["guided_drills"]) >= 3
    assert len(lesson["common_mistakes"]) >= 5
    assert len(lesson["completion_criteria"]) >= 6
    assert len(lesson["self_review_questions"]) >= 5
    assert all(item["explanation"].strip() for item in lesson["steps"])


def test_packaged_lessons_use_unique_stable_identifiers():
    lessons = [json.loads(path.read_text(encoding="utf-8")) for path in CONTENT.glob("*.json")]
    identities = [(lesson["id"], lesson["version"]) for lesson in lessons]
    assert len(identities) == len(set(identities))
    assert all(lesson["schema_version"] == 1 for lesson in lessons)
