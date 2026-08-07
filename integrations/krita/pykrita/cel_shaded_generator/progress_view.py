"""Host-neutral text rendering for the tutor docker's private progress section."""

from __future__ import annotations


def format_progress(snapshot, show_raw_measurements=True):
    if not isinstance(snapshot, dict) or not isinstance(show_raw_measurements, bool):
        raise ValueError("progress display input is invalid")
    if not snapshot.get("retain_learning_progress", False):
        return "Learning-progress retention is disabled for this project."
    attempts = [
        attempt
        for exercise in snapshot.get("exercises", [])
        for attempt in exercise.get("attempts", [])
    ]
    reviews = [review for attempt in attempts for review in attempt.get("reviews", [])]
    lines = [f"Attempts: {len(attempts)} · Reviews: {len(reviews)}"]
    dashboard = snapshot.get("capstone_dashboard", {})
    if dashboard.get("attempt_count", 0):
        lines.append(
            "Capstone: "
            + str(dashboard["review_count"])
            + " reviews · "
            + str(dashboard["pending_decision_count"])
            + " pending decisions"
        )
        for rubric in dashboard.get("rubrics", []):
            lines.append(
                "• "
                + rubric["rubric_id"]
                + " @ "
                + rubric["rubric_version"]
                + ": "
                + rubric["suggestion_decision"]
            )
    recommended = snapshot.get("recommended_exercise_id")
    if recommended:
        lines.append("Recommended next: " + recommended.replace("-", " "))
    if not reviews:
        lines.append("Complete a review to see improvement trends.")
        return "\n".join(lines)
    latest = reviews[-1]
    if len(reviews) > 1 and _identity(reviews[-2]) == _identity(latest):
        before = reviews[-2].get("measurements", {})
        after = latest.get("measurements", {})
        improved = []
        declined = []
        for key in sorted(set(before) & set(after)):
            if not _is_normalized_score(key):
                continue
            delta = after[key] - before[key]
            if delta > 1e-6:
                improved.append(key.replace("_", " "))
            elif delta < -1e-6:
                declined.append(key.replace("_", " "))
        lines.append("Improved: " + (", ".join(improved) if improved else "none yet"))
        lines.append("Needs attention: " + (", ".join(declined) if declined else "no decline"))
    elif len(reviews) > 1:
        lines.append("Latest review is not version-compatible with the previous review.")
    if show_raw_measurements:
        lines.append("Latest normalized measurements:")
        normalized = {
            key: value
            for key, value in latest.get("measurements", {}).items()
            if _is_normalized_score(key)
        }
        lines.extend(
            f"• {key.replace('_', ' ')}: {float(value):.2f}"
            for key, value in sorted(normalized.items())
        )
        if not normalized:
            lines.append("• No normalized measurements available.")
    return "\n".join(lines)


def _identity(review):
    return tuple(
        review.get(key)
        for key in (
            "exercise_version",
            "method_id",
            "rubric_id",
            "rubric_version",
        )
    )


def _is_normalized_score(key):
    return key.endswith("_consistency") or key in {"chin_centering", "jaw_symmetry"}
