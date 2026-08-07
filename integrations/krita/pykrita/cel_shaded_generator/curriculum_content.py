"""Load and render versioned offline lessons without depending on Krita or Qt."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

LESSON_ORDER = (
    "anime-head-front-construction",
    "anime-head-orientation",
    "anime-head-volume-jaw",
    "anime-head-eyes",
    "anime-head-features",
    "anime-head-asymmetry",
    "anime-head-variation",
    "anime-head-cel-values",
    "anime-head-review",
)


def load_lessons(content_directory):
    root = Path(content_directory)
    lessons = []
    for path in sorted(root.glob("*.json")):
        lesson = json.loads(path.read_text(encoding="utf-8"))
        _validate_lesson(lesson, root)
        lessons.append(lesson)
    order = {identifier: index for index, identifier in enumerate(LESSON_ORDER)}
    lessons.sort(key=lambda item: (order.get(item["exercise_id"], len(order)), item["title"]))
    return lessons


def render_lesson_text(lesson):
    sections = [lesson["summary"]]
    _append_list(sections, "Learning objectives", lesson.get("learning_objectives", []))
    _append_named(sections, "Theory", lesson.get("theory", []), "explanation")
    _append_named(sections, "Steps", lesson["steps"], "explanation")
    drills = [
        f"{item['title']} ({item['repetitions']} repetitions): {item['instructions']}"
        for item in lesson.get("guided_drills", [])
    ]
    _append_list(sections, "Guided drills", drills)
    mistakes = [
        f"{item['symptom']} Cause: {item['cause']} Correction: {item['correction']}"
        for item in lesson.get("common_mistakes", [])
    ]
    _append_list(sections, "Common mistakes", mistakes)
    _append_list(sections, "Completion checklist", lesson["completion_criteria"])
    _append_list(sections, "Self-review", lesson.get("self_review_questions", []))
    sections.append("Practice\n" + lesson["practice_prompt"])
    if lesson.get("media"):
        sections.append("Offline diagrams\n• " + "\n• ".join(lesson["media"]))
    return "\n\n".join(sections)


def adjacent_index(current, count, offset):
    if count < 1 or not 0 <= current < count:
        raise ValueError("lesson navigation state is invalid")
    return max(0, min(count - 1, current + offset))


def _validate_lesson(lesson, root):
    required = (
        "id",
        "exercise_id",
        "version",
        "method_id",
        "title",
        "summary",
        "steps",
        "completion_criteria",
        "practice_prompt",
    )
    if not isinstance(lesson, dict) or any(not lesson.get(key) for key in required):
        raise ValueError("packaged lesson is incomplete")
    for media in lesson.get("media", []):
        path = PurePosixPath(media)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            raise ValueError("lesson media must be a packaged relative file")


def _append_list(sections, title, items):
    if items:
        sections.append(title + "\n• " + "\n• ".join(items))


def _append_named(sections, title, items, body_key):
    if items:
        sections.append(
            title + "\n" + "\n".join(f"{item['title']}\n{item[body_key]}" for item in items)
        )
