"""#746: report-card wiring in LoRATrainTab — the success path shows the
card when the run recorded events, other paths keep the old boxes, and
dataset findings feed the suggestion when an advisor panel is attached."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QLabel

from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    with patch("gui.src.tabs.models.delta.lora_train_tab.QMessageBox") as mock_box:
        yield mock_box


@pytest.fixture
def tab(q_app):
    widget = LoRATrainTab()
    yield widget
    widget.close()


def _write_run(tmp_path, monkeypatch, losses, run_id="cardrun"):
    monkeypatch.setenv("ITK_TRAINING_RUNS_ROOT", str(tmp_path))
    from middleware.src.core import training_runs

    run_dir = training_runs.start_run(
        runs_root=tmp_path, run_id=run_id, output_name="o", engine="loha", model_id="m",
        config={},
    )
    with open(training_runs.events_path(run_dir), "w", encoding="utf-8") as fh:
        for i, loss in enumerate(losses):
            fh.write(json.dumps({"step": i + 1, "epoch": 1, "ts": 1000.0 + i, "loss": loss}) + "\n")
    return str(run_dir)


def _shown_card(tab):
    from PySide6.QtTest import QTest
    for _ in range(100):
        if getattr(tab, "_report_worker", None) is None:
            break
        QTest.qWait(20)
    dialog = getattr(tab, "_report_card_dialog", None)
    return dialog


def test_success_with_events_shows_card_instead_of_message_box(tab, tmp_path, monkeypatch, _no_modal_dialogs):
    run_dir = _write_run(
        tmp_path, monkeypatch,
        [1.0 - i * 0.08 for i in range(20)],
    )
    tab.training_finished_signal.emit("success", "done", run_dir)

    dialog = _shown_card(tab)
    assert dialog is not None
    _no_modal_dialogs.information.assert_not_called()
    dialog.close()


def test_success_without_events_falls_back_to_message_box(tab, tmp_path, monkeypatch, _no_modal_dialogs):
    monkeypatch.setenv("ITK_TRAINING_RUNS_ROOT", str(tmp_path))
    from middleware.src.core import training_runs

    run_dir = training_runs.start_run(
        runs_root=tmp_path, run_id="emptyrun", output_name="o", engine="loha", model_id="m",
        config={},
    )
    tab.training_finished_signal.emit("success", "done", str(run_dir))

    assert _shown_card(tab) is None
    _no_modal_dialogs.information.assert_called_once()


def test_success_without_run_dir_keeps_message_box(tab, _no_modal_dialogs):
    tab.training_finished_signal.emit("success", "done", "")
    assert _shown_card(tab) is None
    _no_modal_dialogs.information.assert_called_once()


def test_cancel_and_error_paths_unaffected(tab, _no_modal_dialogs):
    tab.training_finished_signal.emit("cancel", "stopped", "/some/run")
    _no_modal_dialogs.warning.assert_called_once()
    tab.training_finished_signal.emit("error", "boom", "/some/run")
    _no_modal_dialogs.critical.assert_called_once()
    assert _shown_card(tab) is None


def test_advisor_findings_feed_the_suggestion(tab, tmp_path, monkeypatch):
    run_dir = _write_run(tmp_path, monkeypatch, [1.0 - i * 0.08 for i in range(20)])
    finding = SimpleNamespace(
        category="duplicates", severity="warning",
        title="2 identical files", paths=("a", "b"),
    )
    monkeypatch.setattr(tab._advisor_panel, "findings", lambda: [finding])

    tab.training_finished_signal.emit("success", "done", run_dir)

    dialog = _shown_card(tab)
    assert dialog is not None
    labels = [w.text() for w in dialog.findChildren(QLabel)]
    assert any("near-duplicate" in text for text in labels)
    dialog.close()


def test_card_reads_real_run_record_metrics(tab, tmp_path, monkeypatch):
    run_dir = _write_run(tmp_path, monkeypatch, [1.0 - i * 0.08 for i in range(20)])
    tab.training_finished_signal.emit("success", "done", run_dir)
    dialog = _shown_card(tab)
    assert dialog is not None
    labels = [w.text() for w in dialog.findChildren(QLabel)]
    assert any("Loss" in text and "down" in text for text in labels)
    dialog.close()
