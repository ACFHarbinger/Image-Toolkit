"""Validation for fully authored offline curriculum content."""

import importlib.util
import json
from pathlib import Path

import pytest

CONTENT = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/content"


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


def test_lesson_loader_orders_navigation_and_renders_full_content():
    module = _module()
    lessons = module.load_lessons(CONTENT)
    assert [lesson["exercise_id"] for lesson in lessons] == [
        "anime-head-front-construction",
        "anime-head-orientation",
        "anime-head-volume-jaw",
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
