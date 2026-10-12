"""Bounded guidance conversation memory (#754)."""
from dataclasses import dataclass

from backend.src.core.guidance_trajectory import (
    MAX_STORED_STEPS,
    STRUCTURAL_HINT,
    AppliedChange,
    GuidanceTrajectory,
    TrajectoryStep,
    append_step,
    bind_variant,
    build_requeue_trajectory,
    changes_from_verdicts,
    expected_effect,
    format_for_advisor,
    load_trajectory,
    record_verdict,
    save_trajectory,
    should_steer_structural,
    trajectory_from_record,
    trajectory_sidecar_path,
    truncate_steps,
    unresolved_count,
)


def _change(node="6", name="cfg", old=8.5, new=6.0, reason="reduce oversat"):
    return AppliedChange(node, name, old, new, reason)


def _step(n, verdict=None, parent="p0"):
    return TrajectoryStep(
        parent_prompt_id=parent if n == 1 else f"v{n - 1}",
        variant_prompt_id=f"v{n}",
        feedback="too sharp" if n == 1 else "",
        expected=f"try {n}",
        applied=(_change(new=6.0 + n),),
        verdict=verdict,
    )


def test_applied_change_summary_matches_overlay_shape():
    assert _change().summary() == "cfg: 8.5 → 6.0 (node #6)"


def test_changes_from_verdicts_reads_schema_rows():
    @dataclass
    class Change:
        node_id: str
        input_name: str
        from_value: object
        to_value: object
        reason: str = ""

    @dataclass
    class Row:
        change: object

    rows = [Row(Change("6", "cfg", 8.5, 6.0, "softer"))]
    applied = changes_from_verdicts(rows)
    assert len(applied) == 1
    assert applied[0].to_dict()["to"] == 6.0
    assert expected_effect(applied) == "softer"


def test_truncate_keeps_first_and_latest():
    steps = tuple(_step(i) for i in range(1, 8))
    kept = truncate_steps(steps, max_steps=5)
    assert len(kept) == 5
    assert kept[0].variant_prompt_id == "v1"
    assert [s.variant_prompt_id for s in kept[1:]] == ["v4", "v5", "v6", "v7"]
    assert truncate_steps(steps[:3]) == steps[:3]


def test_append_step_truncates_to_cap():
    traj = GuidanceTrajectory(root_prompt_id="p0")
    for i in range(1, MAX_STORED_STEPS + 3):
        traj = append_step(traj, _step(i))
    assert len(traj.steps) == MAX_STORED_STEPS
    assert traj.steps[0].feedback == "too sharp"
    assert traj.steps[-1].variant_prompt_id == f"v{MAX_STORED_STEPS + 2}"


def test_record_verdict_and_structural_steer():
    traj = GuidanceTrajectory(root_prompt_id="p0")
    for i in range(1, 4):
        traj = append_step(traj, _step(i))
    assert not should_steer_structural(traj)
    traj = record_verdict(traj, "same", variant_prompt_id="v1")
    traj = record_verdict(traj, "worse", variant_prompt_id="v2")
    traj = record_verdict(traj, "unsure", variant_prompt_id="v3")
    assert unresolved_count(traj) == 3
    assert should_steer_structural(traj)
    payload = format_for_advisor(traj)
    assert payload["steer_structural"] is True
    assert payload["hint"] == STRUCTURAL_HINT
    assert payload["steps"][0]["verdict"] == "same"


def test_better_verdict_does_not_count_as_unresolved():
    traj = append_step(GuidanceTrajectory(root_prompt_id="p0"), _step(1))
    traj = record_verdict(traj, "better")
    assert unresolved_count(traj) == 0
    assert format_for_advisor(traj)["hint"] is None


def test_unknown_verdict_is_rejected():
    traj = append_step(GuidanceTrajectory(root_prompt_id="p0"), _step(1))
    try:
        record_verdict(traj, "maybe")
    except ValueError as exc:
        assert "maybe" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_bind_variant_stamps_latest_prompt_id():
    traj = append_step(
        GuidanceTrajectory(root_prompt_id="p0"),
        TrajectoryStep(parent_prompt_id="p0", applied=(_change(),)),
    )
    bound = bind_variant(traj, "new-pid")
    assert bound.latest.variant_prompt_id == "new-pid"
    assert bind_variant(bound, "new-pid") is bound


def test_build_requeue_trajectory_appends_selected_rows():
    existing = append_step(GuidanceTrajectory(root_prompt_id="p0"), _step(1, verdict="same"))

    @dataclass
    class Change:
        node_id: str = "6"
        input_name: str = "steps"
        from_value: object = 20
        to_value: object = 28
        reason: str = "more detail"

    @dataclass
    class Row:
        change: object = None

        def __post_init__(self):
            self.change = Change()

    traj = build_requeue_trajectory(
        existing=existing,
        parent_prompt_id="v1",
        selected=[Row()],
        feedback="still muddy",
    )
    assert len(traj.steps) == 2
    assert traj.latest.feedback == "still muddy"
    assert traj.latest.expected == "more detail"
    assert traj.latest.applied[0].input_name == "steps"


def test_sidecar_roundtrip(tmp_path):
    traj = append_step(GuidanceTrajectory(root_prompt_id="abc/def"), _step(1, parent="abc/def"))
    path = trajectory_sidecar_path(tmp_path, traj.root_prompt_id)
    save_trajectory(path, traj)
    loaded = load_trajectory(path)
    assert loaded.to_dict() == traj.to_dict()
    assert load_trajectory(tmp_path / "missing.json") is None


def test_trajectory_from_record_ignores_non_dicts():
    assert trajectory_from_record(None) is None
    assert trajectory_from_record(type("R", (), {"guidance_trajectory": "nope"})()) is None
    raw = GuidanceTrajectory(root_prompt_id="p0").to_dict()
    loaded = trajectory_from_record(type("R", (), {"guidance_trajectory": raw})())
    assert loaded.root_prompt_id == "p0"
