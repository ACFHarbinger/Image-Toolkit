"""Validation for fully authored offline curriculum content."""

import importlib.util
import json
from pathlib import Path

import pytest

CONTENT = Path(__file__).parents[3] / "integrations/krita/pykrita/cel_shaded_generator/content"


def _module():
    path = CONTENT.parent / "curriculum_content.py"
    spec = importlib.util.spec_from_file_location("krita_curriculum_content", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_head_orientation_lesson_is_complete_and_versioned():
    lesson = json.loads((CONTENT / "head_orientation.json").read_text(encoding="utf-8"))

    assert lesson["id"] == "anime-head-orientation"
    assert lesson["exercise_id"] == "anime-head-orientation"
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
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_packaged_lessons_use_unique_stable_identifiers():
    lessons = [json.loads(path.read_text(encoding="utf-8")) for path in CONTENT.glob("*.json")]
    identities = [(lesson["id"], lesson["version"]) for lesson in lessons]
    assert len(identities) == len(set(identities))
    assert all(lesson["schema_version"] == 1 for lesson in lessons)


def test_cranial_volume_jaw_lesson_is_fully_authored():
    lesson = json.loads((CONTENT / "cranial_volume_jaw.json").read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == "anime-head-volume-jaw"
    assert lesson["prerequisite_ids"] == ["anime-head-orientation"]
    assert len(lesson["learning_objectives"]) >= 5
    assert len(lesson["theory"]) >= 4
    assert len(lesson["steps"]) >= 7
    assert len(lesson["guided_drills"]) >= 3
    assert len(lesson["common_mistakes"]) >= 5
    assert len(lesson["completion_criteria"]) >= 6
    assert len(lesson["self_review_questions"]) >= 5
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_eye_placement_lesson_is_fully_authored():
    lesson = json.loads((CONTENT / "eye_placement.json").read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == "anime-head-eyes"
    assert lesson["prerequisite_ids"] == ["anime-head-volume-jaw"]
    assert len(lesson["learning_objectives"]) >= 6
    assert len(lesson["theory"]) >= 5
    assert len(lesson["steps"]) >= 8
    assert len(lesson["guided_drills"]) >= 3
    assert len(lesson["common_mistakes"]) >= 6
    assert len(lesson["completion_criteria"]) >= 7
    assert len(lesson["self_review_questions"]) >= 6
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_feature_placement_lesson_is_fully_authored_with_equal_ear_scope():
    lesson = json.loads((CONTENT / "feature_placement.json").read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == "anime-head-features"
    assert lesson["prerequisite_ids"] == ["anime-head-eyes"]
    assert len(lesson["learning_objectives"]) >= 6
    assert len(lesson["theory"]) >= 5
    assert len(lesson["steps"]) >= 9
    assert len(lesson["guided_drills"]) >= 4
    assert len(lesson["common_mistakes"]) >= 7
    assert len(lesson["completion_criteria"]) >= 8
    assert len(lesson["self_review_questions"]) >= 7
    assert sum("ear" in item["title"].lower() for item in lesson["steps"]) >= 2
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_controlled_asymmetry_lesson_is_fully_authored():
    lesson = json.loads((CONTENT / "controlled_asymmetry.json").read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == "anime-head-asymmetry"
    assert lesson["prerequisite_ids"] == ["anime-head-features"]
    assert len(lesson["learning_objectives"]) >= 6
    assert len(lesson["theory"]) >= 5
    assert len(lesson["steps"]) >= 8
    assert len(lesson["guided_drills"]) >= 4
    assert len(lesson["common_mistakes"]) >= 6
    assert len(lesson["completion_criteria"]) >= 8
    assert len(lesson["self_review_questions"]) >= 7
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_character_variation_lesson_is_fully_authored():
    lesson = json.loads((CONTENT / "character_variation.json").read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == "anime-head-variation"
    assert lesson["prerequisite_ids"] == ["anime-head-asymmetry"]
    assert len(lesson["learning_objectives"]) >= 6
    assert len(lesson["theory"]) >= 5
    assert len(lesson["steps"]) >= 9
    assert len(lesson["guided_drills"]) >= 4
    assert len(lesson["common_mistakes"]) >= 7
    assert len(lesson["completion_criteria"]) >= 8
    assert len(lesson["self_review_questions"]) >= 7
    assert all((CONTENT / path).is_file() for path in lesson["media"])


@pytest.mark.parametrize(
    "filename,exercise_id,prerequisite",
    [
        ("cel_value_grouping.json", "anime-head-cel-values", "anime-head-variation"),
        ("comprehensive_review.json", "anime-head-review", "anime-head-cel-values"),
    ],
)
def test_final_lessons_are_fully_authored(filename, exercise_id, prerequisite):
    lesson = json.loads((CONTENT / filename).read_text(encoding="utf-8"))
    assert lesson["exercise_id"] == exercise_id
    assert lesson["prerequisite_ids"] == [prerequisite]
    assert len(lesson["learning_objectives"]) >= 6
    assert len(lesson["theory"]) >= 5
    assert len(lesson["steps"]) >= 9
    assert len(lesson["guided_drills"]) >= 4
    assert len(lesson["common_mistakes"]) >= 7
    assert len(lesson["completion_criteria"]) >= 8
    assert len(lesson["self_review_questions"]) >= 7
    assert all((CONTENT / path).is_file() for path in lesson["media"])


def test_lesson_loader_orders_navigation_and_renders_full_content():
    module = _module()
    lessons = module.load_lessons(CONTENT)
    assert [lesson["exercise_id"] for lesson in lessons] == [
        "anime-head-front-construction",
        "anime-head-orientation",
        "anime-head-volume-jaw",
        "anime-head-eyes",
        "anime-head-features",
        "anime-head-asymmetry",
        "anime-head-variation",
        "anime-head-cel-values",
        "anime-head-review",
    ]
    rendered = module.render_lesson_text(lessons[1])
    assert "Learning objectives" in rendered
    assert "Common mistakes" in rendered
    assert "Offline diagrams" in rendered
    assert module.adjacent_index(0, 2, -1) == 0
    assert module.adjacent_index(0, 2, 1) == 1
    assert module.adjacent_index(1, 2, 1) == 1
    with pytest.raises(ValueError, match="navigation state"):
        module.adjacent_index(-1, 2, 1)
