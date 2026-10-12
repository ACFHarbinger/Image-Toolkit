"""#747: checkpoint tournament dialog — blind display, voting flow, fatigue
cap, resume, promotion; report-card entry point."""
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.src.core import checkpoint_tournament as ct
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPushButton

from gui.src.components.dialogs.checkpoint_tournament_dialog import (
    SESSION_CAP,
    CheckpointTournamentDialog,
    _BlindCompareView,
)
from gui.src.components.dialogs.training_report_card_dialog import (
    TrainingReportCardDialog,
)

pytestmark = pytest.mark.gui


def _make_run(tmp_path: Path, *, n_checkpoints: int = 2, n_grids: int = 3) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    final = out / "demo.safetensors"
    final.write_bytes(b"")
    for epoch in range(n_checkpoints):
        ckpt = out / f"checkpoint-epoch{epoch:04d}"
        ckpt.mkdir()
        (ckpt / "adapter_model.safetensors").write_bytes(b"")
    run_dir = tmp_path / "20261012-120000-demo-deadbeef"
    run_dir.mkdir()
    (run_dir / "record.json").write_text(
        json.dumps(
            {
                "run_id": "20261012-120000-demo-deadbeef",
                "lora_path": str(final),
                "config": {"output_dir": str(out), "output_name": "demo"},
            }
        ),
        encoding="utf-8",
    )
    events = [
        {"step": 10, "epoch": 0, "loss": 0.4},
        {"step": 20, "epoch": 1, "loss": 0.3},
        {"step": 30, "epoch": 1, "loss": 0.2},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    if n_grids:
        samples = run_dir / "samples"
        samples.mkdir()
        for i in range(n_grids):
            step = (i + 1) * 10
            assert QPixmap(64, 64).save(str(samples / f"step-{step:06d}.png"), "PNG")
    return run_dir


@pytest.fixture
def run_dir(q_app, tmp_path):
    return _make_run(tmp_path)


@pytest.fixture
def dialog(q_app, run_dir):
    dlg = CheckpointTournamentDialog(str(run_dir), rng=random.Random(3))
    yield dlg
    dlg.close()


def _click(dialog, text):
    for btn in dialog.findChildren(QPushButton):
        if btn.text() == text and btn.isEnabled():
            btn.click()
            return btn
    raise AssertionError(f"no enabled button {text!r}")


# ---------------------------------------------------------------------------
# blind display
# ---------------------------------------------------------------------------

def test_opens_with_blind_pair(dialog):
    view = dialog.findChild(_BlindCompareView)
    assert view is not None
    assert [p.header.text() for p in view.panes] == ["A", "B"]
    assert not view.btn_overlay.isVisibleTo(view)
    assert not view.btn_diff.isVisibleTo(view)


def test_pane_headers_never_leak_filenames(dialog):
    view = dialog.findChild(_BlindCompareView)
    for pane in view.panes:
        assert "step-" not in pane.header.text()
        assert ".png" not in pane.header.text()


# ---------------------------------------------------------------------------
# voting flow
# ---------------------------------------------------------------------------

def test_voting_updates_standings_and_persists(dialog, run_dir):
    assert dialog._table.rowCount() == 3  # epoch 0000, epoch 0001, final
    assert not dialog._promote_btn.isEnabled()  # no votes yet
    _click(dialog, "← A wins")
    assert (run_dir / ct.STATE_FILE_NAME).exists()
    assert "1 recorded" in dialog._note_label.text()
    assert dialog._promote_btn.isEnabled()
    state = ct.load_state(run_dir)
    assert ct.total_games(state) == 1


def test_skip_advances_without_recording(dialog, run_dir):
    first_pair = dialog._current_pair
    _click(dialog, "Skip (N)")
    assert dialog._current_pair not in (None, first_pair)
    state = ct.load_state(run_dir)
    assert state is None or ct.total_games(state) == 0
    assert "0 recorded" in dialog._note_label.text()


def test_tie_counts_half(dialog, run_dir):
    _click(dialog, "Tie (T)")
    state = ct.load_state(run_dir)
    keys = [h["a"] for h in state.history] + [h["b"] for h in state.history]
    assert state.history[0]["result"] == ct.RESULT_TIE
    assert all(state.entries[k].rating == pytest.approx(1500.0) for k in set(keys))


def test_repeat_pair_never_suggested(dialog, run_dir):
    seen = set()
    for _ in range(3):
        pair = dialog._current_pair
        assert pair is not None
        seen.add(frozenset(pair))
        _click(dialog, "← A wins")
    assert len(seen) == 3  # 3 entries → 3 distinct pairs


def test_fatigue_cap_ends_sitting(q_app, run_dir):
    dlg = CheckpointTournamentDialog(str(run_dir), rng=random.Random(3), session_cap=3)
    for _ in range(3):
        _click(dlg, "← A wins")
    assert "Sitting complete" in " ".join(
        w.text() for w in dlg.findChildren(QLabel)
    )
    assert not dlg._vote_a.isEnabled()
    state = ct.load_state(run_dir)
    assert ct.total_games(state) == 3
    dlg.close()


def test_session_cap_default_is_twelve():
    assert SESSION_CAP == 12


# ---------------------------------------------------------------------------
# resume
# ---------------------------------------------------------------------------

def test_resume_restores_saved_ratings(q_app, run_dir):
    dlg = CheckpointTournamentDialog(str(run_dir), rng=random.Random(3))
    for _ in range(2):
        _click(dlg, "← A wins")
    ratings_before = {r.key: r.rating for r in ct.standings(dlg._state)}
    dlg.close()

    resumed = CheckpointTournamentDialog(str(run_dir), rng=random.Random(3))
    ratings_after = {r.key: r.rating for r in ct.standings(resumed._state)}
    assert ratings_after == pytest.approx(ratings_before)
    assert "2 recorded" in resumed._note_label.text()
    resumed.close()


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------

def test_promote_emits_pin_and_records_provenance(q_app, run_dir, monkeypatch):
    monkeypatch.setattr(
        "gui.src.components.dialogs.checkpoint_tournament_dialog.QMessageBox.information",
        lambda *a, **k: None,
    )
    dlg = CheckpointTournamentDialog(str(run_dir), rng=random.Random(3))
    pins = []
    dlg.promote_requested.connect(pins.append)
    for _ in range(2):
        _click(dlg, "← A wins")
    _click(dlg, "Promote Winner…")

    assert len(pins) == 1
    pin = pins[0]
    assert pin.artifact_path.endswith("adapter_model.safetensors")
    assert pin.config["sub_config"]["lora_path"] == pin.artifact_path
    assert pin.config["selected_model"] == "anything"
    assert "tournament winner" in pin.label
    assert pin.run_id.startswith("20261012-120000-demo-deadbeef:epoch-")

    state = ct.load_state(run_dir)
    assert state.promoted is not None
    assert state.promoted["key"] in state.entries
    assert state.promoted["checkpoint_path"] == pin.artifact_path or state.promoted[
        "checkpoint_path"
    ] != ""
    dlg.close()


def test_promote_without_votes_is_disabled(dialog):
    assert not dialog._promote_btn.isEnabled()


def test_forward_promoted_pin_walks_parent_chain():
    from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

    noted = []
    fake_parent = SimpleNamespace(note_run=noted.append, parent=lambda: None)
    fake_self = SimpleNamespace(parent=lambda: fake_parent, window=lambda: None)
    LoRATrainTab._forward_promoted_pin(fake_self, "pin")
    assert noted == ["pin"]


def test_forward_promoted_pin_no_spine_is_silent():
    from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

    fake_self = SimpleNamespace(parent=lambda: None, window=lambda: None)
    LoRATrainTab._forward_promoted_pin(fake_self, "pin")  # must not raise


# ---------------------------------------------------------------------------
# entry point: the report card button
# ---------------------------------------------------------------------------

def test_report_card_shows_tournament_button_for_ready_run(q_app, run_dir):
    from backend.src.core.training_report import (
        STATUS_GOOD,
        ReportCard,
        ReportVerdict,
    )

    card = ReportCard(verdicts=(), suggestion=ReportVerdict("x", STATUS_GOOD, "y"), step_count=5)
    dlg = TrainingReportCardDialog(card, run_dir=str(run_dir))
    emitted = []
    dlg.start_tournament_requested.connect(emitted.append)
    labels = [b.text() for b in dlg.findChildren(QPushButton)]
    assert "Start Tournament…" in labels
    for btn in dlg.findChildren(QPushButton):
        if btn.text() == "Start Tournament…":
            btn.click()
    assert emitted == [str(run_dir)]
    dlg.close()


def test_report_card_hides_tournament_button_without_inputs(q_app, tmp_path):
    from backend.src.core.training_report import (
        STATUS_GOOD,
        ReportCard,
        ReportVerdict,
    )

    bare = _make_run(tmp_path, n_checkpoints=1, n_grids=0)
    card = ReportCard(verdicts=(), suggestion=ReportVerdict("x", STATUS_GOOD, "y"), step_count=5)
    dlg = TrainingReportCardDialog(card, run_dir=str(bare))
    labels = [b.text() for b in dlg.findChildren(QPushButton)]
    assert "Start Tournament…" not in labels
    dlg.close()


def test_insufficient_inputs_explains_itself(q_app, tmp_path):
    bare = _make_run(tmp_path, n_checkpoints=0, n_grids=1)  # only "final" → 1 entry
    dlg = CheckpointTournamentDialog(str(bare), rng=random.Random(3))
    assert dlg._state is None
    joined = " ".join(w.text() for w in dlg.findChildren(QLabel))
    assert "Not enough to compare" in joined
    assert not dlg._vote_a.isEnabled()
    assert not dlg._promote_btn.isEnabled()
    dlg.close()
