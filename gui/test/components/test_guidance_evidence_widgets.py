"""#753: evidence chips, confidence badge, abstention panel."""
import pytest
from backend.src.core import guidance_evidence as ge
from backend.src.core.guidance_schema import EvidenceRef
from gui.src.components.guidance.guidance_evidence_widgets import (
    TRAIN_MODULE_ID,
    AbstentionPanel,
    ConfidenceBadge,
    EvidenceChipBar,
    EvidenceRowExtras,
)
from PySide6.QtWidgets import QLabel, QToolButton

pytestmark = pytest.mark.gui


def _resolved(kind="tournament", **kw):
    return ge.ResolvedEvidence(ref=EvidenceRef(kind=kind, ref={}), **kw)


# ---------------------------------------------------------------------------
# ConfidenceBadge
# ---------------------------------------------------------------------------

def test_badge_bands(q_app):
    badge = ConfidenceBadge(0.9)
    assert "High" in badge.text()
    assert "#3a9d6e" in badge.styleSheet()
    badge.set_score(0.6)
    assert "Medium" in badge.text()
    assert "#c9a227" in badge.styleSheet()
    badge.set_score(0.2)
    assert "Low" in badge.text()
    assert "#c0392b" in badge.styleSheet()
    assert "0.20" in badge.toolTip()


# ---------------------------------------------------------------------------
# EvidenceChipBar
# ---------------------------------------------------------------------------

def test_chip_bar_renders_titles_and_stale_marks(q_app):
    bar = EvidenceChipBar(
        (
            _resolved(title="Blind tournament: epoch 0000 at ELO 1612", target_dir="/tmp"),
            _resolved(title="OCR read", detail="x", stale=True),
        )
    )
    assert bar.chip_texts() == ["Blind tournament: epoch 0000 at ELO 1612", "OCR read (stale)"]
    buttons = bar.findChildren(QToolButton)
    assert buttons[0].isEnabled()  # has target_dir → clickable
    assert not buttons[1].isEnabled()  # summary-only stale → not clickable
    bar.deleteLater()


def test_chip_bar_empty_hides_itself(q_app):
    bar = EvidenceChipBar(())
    assert not bar.isVisibleTo(bar.parent()) or bar.chip_texts() == []
    bar.deleteLater()


def test_chip_click_with_paths_emits_signal(q_app, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    bar = EvidenceChipBar((_resolved(kind="advisor_finding", title="Advisor", paths=(str(img),)),))
    got = []
    bar.paths_requested.connect(got.append)
    bar.findChildren(QToolButton)[0].click()
    assert got == [(str(img),)]
    bar.deleteLater()


def test_chip_click_with_dir_opens_location(q_app, tmp_path, monkeypatch):
    opened = []
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(
        QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString()) or True)
    )
    bar = EvidenceChipBar((_resolved(title="Run x", target_dir=str(tmp_path)),))
    bar.findChildren(QToolButton)[0].click()
    assert opened == [QUrl.fromLocalFile(str(tmp_path)).toString()]
    bar.deleteLater()


# ---------------------------------------------------------------------------
# EvidenceRowExtras
# ---------------------------------------------------------------------------

def test_row_extras_badge_and_chips(q_app, tmp_path):
    change = type("Ch", (), {
        "node_id": "n1",
        "input_name": "cfg",
        "to_value": 6.0,
        "confidence": None,
        "evidence": (EvidenceRef(kind="ocr", ref={}, summary="reads 8.5"),),
    })()
    row = EvidenceRowExtras(change, None)
    row._thread.join(2)
    q_app.processEvents()
    # One uncorroborated model-reported signal, no verified premise: the
    # rubric's exact 0.5 → honestly "might", i.e. medium, not low.
    assert "Medium" in row.badge.text()
    assert row.chips.chip_texts() == ["OCR read: reads 8.5"]
    row.deleteLater()


# ---------------------------------------------------------------------------
# AbstentionPanel
# ---------------------------------------------------------------------------

def test_abstention_panel_renders_needs(q_app):
    panel = AbstentionPanel(needs=("more hand-angle variety",), diagnosis="OCR vs VLM disagree")
    texts = [w.text() for w in panel.findChildren(QLabel)]
    joined = " ".join(texts)
    assert "Insufficient evidence" in joined
    assert "more hand-angle variety" in joined
    assert "OCR vs VLM disagree" in joined
    assert not panel._send_btn.isEnabled()  # no paths matched
    panel.deleteLater()


def test_abstention_panel_send_dispatches_intent(q_app, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    published = []

    class FakeHub:
        def publish(self, event):
            published.append(event)

    from gui.src.modules.events import ImportPathsIntent

    needs = ("more variety",)
    evidence = (EvidenceRef(kind="advisor_finding", ref={"paths": [str(img)]}),)
    panel = AbstentionPanel(needs=needs, evidence=evidence, event_hub=FakeHub())
    panel._thread.join(2)
    q_app.processEvents()
    assert panel._send_btn.isEnabled()
    got = []
    panel.pick_list_requested.connect(got.append)
    panel._send_btn.click()
    assert len(published) == 1
    assert isinstance(published[0], ImportPathsIntent)
    assert published[0].module_id == TRAIN_MODULE_ID == "dl.train"
    assert published[0].paths == (str(img),)
    assert got == [(str(img),)]
    panel.deleteLater()


def test_abstention_panel_emits_without_hub(q_app, tmp_path):
    img = tmp_path / "b.png"
    img.write_bytes(b"")
    evidence = (EvidenceRef(kind="advisor_finding", ref={"paths": [str(img)]}),)
    panel = AbstentionPanel(needs=("x",), evidence=evidence)
    panel._thread.join(2)
    q_app.processEvents()
    got = []
    panel.pick_list_requested.connect(got.append)
    panel._send_btn.click()
    assert got == [(str(img),)]
    panel.deleteLater()
