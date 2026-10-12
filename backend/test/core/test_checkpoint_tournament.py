"""#747: checkpoint tournament core — ELO math, pairing, persistence, discovery."""
import json
import math
import random
from pathlib import Path

import pytest

from backend.src.core import checkpoint_tournament as ct
from backend.src.core.checkpoint_tournament import (
    RESULT_A,
    RESULT_B,
    RESULT_TIE,
    SIGNIFICANT_GAMES,
    CheckpointInfo,
    SampleGrid,
    TournamentEntry,
    TournamentState,
    associate_sample,
    attach_state,
    build_entries,
    discover_checkpoints,
    discover_sample_grids,
    expected_score,
    is_significant,
    load_state,
    promote,
    record_result,
    save_state,
    standings,
    suggest_pair,
    uncertainty_margin,
)


def _state(*keys: str) -> TournamentState:
    return TournamentState(
        run_id="run",
        entries={
            k: TournamentEntry(key=k, label=k, checkpoint_path=f"/c/{k}", sample_path=f"/s/{k}.png")
            for k in keys
        },
    )


# ---------------------------------------------------------------------------
# ELO math
# ---------------------------------------------------------------------------

def test_expected_score_midpoint_and_symmetry():
    assert expected_score(1500.0, 1500.0) == pytest.approx(0.5)
    assert expected_score(1600.0, 1500.0) == pytest.approx(1.0 - expected_score(1500.0, 1600.0))


def test_equal_rating_win_moves_16_each_direction():
    state = _state("x", "y")
    assert record_result(state, "x", "y", RESULT_A, ts=1.0)
    assert state.entries["x"].rating == pytest.approx(1516.0)
    assert state.entries["y"].rating == pytest.approx(1484.0)
    assert state.entries["x"].wins == 1 and state.entries["y"].games == 1


def test_tie_scores_half_and_counts():
    state = _state("x", "y")
    record_result(state, "x", "y", RESULT_TIE, ts=1.0)
    assert state.entries["x"].rating == pytest.approx(1500.0)
    assert state.entries["x"].ties == 1 and state.entries["y"].ties == 1


def test_favorite_win_gains_less_than_upset():
    state = _state("x", "y")
    state.entries["x"].rating = 1800.0
    record_result(state, "x", "y", RESULT_A, ts=1.0)
    favorite_gain = state.entries["x"].rating - 1800.0
    state2 = _state("x", "y")
    state2.entries["x"].rating = 1800.0
    record_result(state2, "y", "x", RESULT_A, ts=1.0)  # upset from y's seat
    upset_gain = state2.entries["y"].rating - 1500.0
    assert 0 < favorite_gain < upset_gain


def test_repeat_pair_refused_either_order():
    state = _state("x", "y")
    assert record_result(state, "x", "y", RESULT_A, ts=1.0)
    assert not record_result(state, "y", "x", RESULT_B, ts=2.0)
    assert not record_result(state, "x", "y", RESULT_TIE, ts=3.0)
    assert len(state.history) == 1
    assert state.entries["x"].games == 1


def test_invalid_calls_rejected():
    state = _state("x", "y")
    assert not record_result(state, "x", "x", RESULT_A)
    assert not record_result(state, "x", "nope", RESULT_A)
    assert not record_result(state, "x", "y", "bogus")


# ---------------------------------------------------------------------------
# Pairing + standings
# ---------------------------------------------------------------------------

def test_suggest_pair_exhausts_all_pairs_then_none():
    state = _state("a", "b", "c")
    rng = random.Random(7)
    seen = set()
    for _ in range(3):
        pair = suggest_pair(state, rng)
        assert pair is not None
        seen.add(frozenset(pair))
        assert record_result(state, pair[0], pair[1], RESULT_TIE, ts=1.0)
    assert len(seen) == 3
    assert suggest_pair(state, rng) is None


def test_suggest_pair_is_deterministic_under_seed():
    state = _state("a", "b", "c", "d")
    first = suggest_pair(state, random.Random(42))
    again = suggest_pair(state, random.Random(42))
    assert first == again
    assert first[0] != first[1]


def test_suggest_pair_prefers_close_ratings():
    state = _state("strong", "mid", "weak")
    state.entries["strong"].rating = 1700.0
    state.entries["mid"].rating = 1500.0
    state.entries["weak"].rating = 1200.0
    pair = suggest_pair(state, random.Random(1))
    assert set(pair) == {"strong", "mid"}


def test_suggest_pair_spreads_play_on_rating_ties():
    state = _state("a", "b", "c")
    record_result(state, "a", "b", RESULT_A, ts=1.0)
    pair = set(suggest_pair(state, random.Random(3)))
    assert "c" in pair  # c has 0 games; a-b rematch is refused anyway


def test_suggest_pair_avoids_skipped():
    state = _state("a", "b", "c")
    skip = {frozenset({"a", "b"})}
    for _ in range(2):
        pair = set(suggest_pair(state, random.Random(5), avoid=skip))
        assert pair != {"a", "b"}
        skip.add(frozenset(pair))
    assert suggest_pair(state, random.Random(5), avoid=skip) is None


def test_standings_sorted_with_glicko_lite_margin():
    state = _state("x", "y")
    record_result(state, "x", "y", RESULT_A, ts=1.0)
    rows = standings(state)
    assert [r.key for r in rows] == ["x", "y"]
    assert rows[0].rating == pytest.approx(1516.0)
    assert rows[0].margin == pytest.approx(2 * 350 / math.sqrt(2))
    assert rows[1].margin == pytest.approx(2 * 350 / math.sqrt(2))


def test_uncertainty_shrinks_with_games():
    assert uncertainty_margin(0) == pytest.approx(700.0)
    assert uncertainty_margin(9) < uncertainty_margin(0)


def test_significance_threshold():
    state = _state("x", "y")
    assert not is_significant(state)
    state.history = [{"a": "x", "b": "y", "result": RESULT_TIE}] * SIGNIFICANT_GAMES
    assert is_significant(state)


# ---------------------------------------------------------------------------
# Persistence + resume
# ---------------------------------------------------------------------------

def test_state_round_trip(tmp_path):
    state = _state("x", "y")
    record_result(state, "x", "y", RESULT_A, ts=12.0)
    promote(state, "x", ts=13.0)
    path = save_state(tmp_path, state)
    loaded = load_state(tmp_path)
    assert path.name == ct.STATE_FILE_NAME
    assert loaded is not None
    assert loaded.entries["x"].rating == pytest.approx(1516.0)
    assert loaded.history == state.history
    assert loaded.promoted["key"] == "x"
    assert loaded.promoted["checkpoint_path"] == "/c/x"


def test_load_state_missing_or_corrupt(tmp_path):
    assert load_state(tmp_path) is None
    (tmp_path / ct.STATE_FILE_NAME).write_text("{not json", encoding="utf-8")
    assert load_state(tmp_path) is None
    (tmp_path / ct.STATE_FILE_NAME).write_text(json.dumps([1, 2]), encoding="utf-8")
    assert load_state(tmp_path) is None


def test_attach_state_resumes_ratings_and_prunes_stale_keys(tmp_path):
    state = _state("x", "y", "z")
    record_result(state, "x", "y", RESULT_A, ts=1.0)
    record_result(state, "x", "z", RESULT_B, ts=2.0)
    save_state(tmp_path, state)

    fresh = [
        TournamentEntry(key="x", label="epoch 0000", checkpoint_path="/c/x", sample_path="/s/x.png"),
        TournamentEntry(key="y", label="epoch 0001", checkpoint_path="/c/y", sample_path="/s/y.png"),
        TournamentEntry(key="w", label="epoch 0003", checkpoint_path="/c/w", sample_path="/s/w.png"),
    ]
    merged = attach_state(tmp_path, fresh)
    # x beat y (1516) then lost to z: 1516 + 32·(0 − E(1516,1500)) ≈ 1499.26
    assert merged.entries["x"].rating == pytest.approx(1516.0)
    assert merged.entries["y"].rating == pytest.approx(1484.0)
    assert merged.entries["w"].rating == ct.ELO_START  # new checkpoint
    played = {frozenset((h["a"], h["b"])) for h in merged.history}
    assert frozenset(("x", "y")) in played
    assert all("z" not in pair for pair in played)


def test_attach_state_drops_promotion_for_deleted_checkpoint(tmp_path):
    state = _state("x", "y")
    record_result(state, "x", "y", RESULT_A, ts=1.0)
    promote(state, "y", ts=2.0)
    save_state(tmp_path, state)
    fresh = [
        TournamentEntry(key="x", label="epoch 0000", checkpoint_path="/c/x", sample_path="/s/x.png"),
        TournamentEntry(key="w", label="epoch 0003", checkpoint_path="/c/w", sample_path="/s/w.png"),
    ]
    assert attach_state(tmp_path, fresh).promoted is None


def test_attach_state_without_saved_state_starts_fresh(tmp_path):
    fresh = [
        TournamentEntry(key="x", label="epoch 0000", checkpoint_path="/c/x", sample_path="/s/x.png"),
    ]
    merged = attach_state(tmp_path, fresh)
    assert merged.entries["x"].rating == ct.ELO_START
    assert merged.history == []


def test_promote_records_provenance_fields():
    state = _state("x", "y")
    record_result(state, "x", "y", RESULT_A, ts=1.0)
    prov = promote(state, "x", ts=99.0)
    assert prov["key"] == "x"
    assert prov["label"] == "x"
    assert prov["checkpoint_path"] == "/c/x"
    assert prov["run_id"] == "run"
    assert prov["ts"] == 99.0
    assert prov["games"] == 1
    with pytest.raises(KeyError):
        promote(state, "nope")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _make_run(tmp_path, *, with_final_file=True, with_samples=(), with_events=()):
    out = tmp_path / "out"
    out.mkdir()
    run_dir = tmp_path / "20261012-120000-demo-deadbeef"
    run_dir.mkdir()
    final_path = out / "demo.safetensors"
    if with_final_file:
        final_path.write_bytes(b"")
    record = {
        "run_id": "20261012-120000-demo-deadbeef",
        "lora_path": str(final_path) if with_final_file else "",
        "config": {"output_dir": str(out), "output_name": "demo"},
    }
    (run_dir / "record.json").write_text(json.dumps(record), encoding="utf-8")
    if with_events:
        lines = [json.dumps(ev) for ev in with_events]
        (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if with_samples:
        samples = run_dir / "samples"
        samples.mkdir()
        for step in with_samples:
            (samples / f"step-{step:06d}.png").write_bytes(b"")
    return run_dir, out


def _add_checkpoint(out: Path, epoch: int, *, weights: bool = True) -> None:
    ckpt = out / f"checkpoint-epoch{epoch:04d}"
    ckpt.mkdir()
    if weights:
        (ckpt / "adapter_model.safetensors").write_bytes(b"")


def test_discover_checkpoints_finds_weighted_dirs_and_final(tmp_path):
    run_dir, out = _make_run(tmp_path)
    _add_checkpoint(out, 0)
    _add_checkpoint(out, 2)
    _add_checkpoint(out, 9, weights=False)  # no weights → skipped
    (out / "notes.txt").write_text("x")
    found = discover_checkpoints(run_dir)
    assert [c.key for c in found] == ["epoch-0000", "epoch-0002", "final"]
    assert [c.epoch for c in found] == [0, 2, None]


def test_discover_checkpoints_ignores_missing_output_dir(tmp_path):
    run_dir, out = _make_run(tmp_path)
    import shutil

    shutil.rmtree(out)
    found = discover_checkpoints(run_dir)
    assert found == []  # lora_path's file died with the output dir


def test_discover_checkpoints_ignores_dir_named_like_weights(tmp_path):
    run_dir, out = _make_run(tmp_path, with_final_file=False)
    _add_checkpoint(out, 0)
    (out / "weird.safetensors").mkdir()  # a directory, not a file
    found = discover_checkpoints(run_dir)
    assert [c.key for c in found] == ["epoch-0000"]


def test_discover_sample_grids_parses_and_sorts_steps(tmp_path):
    run_dir, _ = _make_run(tmp_path, with_samples=[40, 10, 25])
    (run_dir / "samples" / "random.png").write_bytes(b"")
    (run_dir / "samples" / "step-abc.png").write_bytes(b"")
    grids = discover_sample_grids(run_dir)
    assert [g.step for g in grids] == [10, 25, 40]
    assert all(g.path.endswith(".png") for g in grids)


def test_discover_sample_grids_missing_dir(tmp_path):
    run_dir, _ = _make_run(tmp_path)
    assert discover_sample_grids(run_dir) == []


def test_associate_sample_requires_exact_epoch_end():
    grids = [SampleGrid(path=f"/s/{s}.png", step=s) for s in (5, 12, 20)]
    upper = {0: 10, 1: 20}
    e0 = associate_sample(CheckpointInfo(key="epoch-0000", label="e0", path="/c", epoch=0), grids, upper)
    e1 = associate_sample(CheckpointInfo(key="epoch-0001", label="e1", path="/c", epoch=1), grids, upper)
    final = associate_sample(CheckpointInfo(key="final", label="f", path="/c", epoch=None), grids, upper)
    assert e0 is None
    assert e1.step == 20
    assert final.step == 20


def test_associate_sample_no_grid_before_epoch_picks_nearest_after():
    grids = [SampleGrid(path="/s/50.png", step=50)]
    got = associate_sample(
        CheckpointInfo(key="epoch-0000", label="e0", path="/c", epoch=0), grids, {0: 10}
    )
    assert got is None  # nothing at or before step 10; caller skips the checkpoint
    assert grids[0].step == 50


def test_epoch_upper_steps_uses_event_epochs():
    events = [
        {"step": 5, "epoch": 0},
        {"step": 10, "epoch": 0},
        {"step": 20, "epoch": 1},
    ]
    assert ct._epoch_upper_steps(events, 2) == {0: 10, 1: 20}


def test_epoch_upper_steps_does_not_guess_without_tags():
    events = [{"step": 10}, {"step": 50}, {"step": 100}]
    assert ct._epoch_upper_steps(events, 2) == {}


def test_build_entries_end_to_end(tmp_path):
    run_dir, out = _make_run(
        tmp_path,
        with_samples=[10, 20, 30],
        with_events=[
            {"step": 10, "epoch": 0, "loss": 0.4},
            {"step": 20, "epoch": 0, "loss": 0.3},
            {"step": 30, "epoch": 1, "loss": 0.2},
        ],
    )
    _add_checkpoint(out, 0)
    _add_checkpoint(out, 1)
    entries = build_entries(run_dir)
    by_key = {e.key: e for e in entries}
    assert set(by_key) == {"epoch-0000", "epoch-0001"}
    assert by_key["epoch-0000"].sample_path.endswith("step-000020.png")
    assert by_key["epoch-0001"].sample_path.endswith("step-000030.png")
    assert len({entry.sample_path for entry in entries}) == len(entries)


def test_build_entries_without_grids_is_empty(tmp_path):
    run_dir, out = _make_run(tmp_path)
    _add_checkpoint(out, 0)
    _add_checkpoint(out, 1)
    assert build_entries(run_dir) == []


def test_build_entries_needs_two(tmp_path):
    run_dir, out = _make_run(tmp_path, with_final_file=False, with_samples=[10])
    _add_checkpoint(out, 0)
    assert build_entries(run_dir) == []  # untagged samples cannot identify a checkpoint


def test_sanitize_label_strips_control_chars():
    assert ct.sanitize_label("epoch 0003<script>") == "epoch 0003script"
    assert ct.sanitize_label("☃") == "checkpoint"  # empty after strip → fallback
    assert ct.sanitize_label("") == "checkpoint"
