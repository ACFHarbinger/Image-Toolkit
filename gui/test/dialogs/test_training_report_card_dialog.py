"""#746: training report card dialog — verdict rows, suggestion banner,
non-modal behavior, run-folder shortcut."""
import pytest
from backend.src.core.training_report import (
    STATUS_GOOD,
    STATUS_WARN,
    ReportCard,
    ReportVerdict,
)
from PySide6.QtWidgets import QLabel, QPushButton

from gui.src.components.dialogs.training_report_card_dialog import (
    TrainingReportCardDialog,
)

pytestmark = pytest.mark.gui


def _card():
    return ReportCard(
        verdicts=(
            ReportVerdict("Did it learn?", STATUS_GOOD, "Loss 72% down (0.41 → 0.11)"),
            ReportVerdict("Is it overfitting?", STATUS_WARN,
                          "Rank utilization at 6/64 — saturated far below the cap"),
        ),
        suggestion=ReportVerdict("What to try next", STATUS_WARN,
                                 "Effective rank saturated at 6/64 — try rank 9"),
        step_count=250,
    )


@pytest.fixture
def dialog(q_app):
    dlg = TrainingReportCardDialog(_card(), run_dir="/tmp/fake-run")
    yield dlg
    dlg.close()


def test_dialog_renders_all_questions(dialog):
    texts = [w.text() for w in dialog.findChildren(QLabel)]
    joined = " ".join(texts)
    assert "Did it learn?" in joined
    assert "Is it overfitting?" in joined
    assert "What to try next" in joined
    assert "Loss 72% down (0.41 → 0.11)" in joined
    assert "try rank 9" in joined


def test_dialog_is_non_modal(dialog):
    assert not dialog.isModal()


def test_run_folder_button_only_with_run_dir(q_app):
    without = TrainingReportCardDialog(_card())
    texts = [w.text() for w in without.findChildren(QPushButton)]
    assert "Open Run Folder" not in texts
    without.close()


def test_status_dots_colored(dialog):
    from gui.src.components.dialogs import training_report_card_dialog as mod

    dots = [
        w for w in dialog.findChildren(QLabel)
        if w.text() in {"●", "○"} and w.toolTip() in {"good", "warn", "bad", "info"}
    ]
    assert len(dots) == 3  # two verdicts + suggestion
    assert any(mod._STATUS_COLORS[d.toolTip()] in d.styleSheet() for d in dots)
    assert any(d.toolTip() == "bad" or d.toolTip() == "warn" for d in dots)
