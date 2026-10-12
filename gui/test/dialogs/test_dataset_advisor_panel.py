"""#744: dataset advisor panel — findings cards, one-click actions,
pending Hydra overrides, and the GPU-lease clustering action.

Deterministic scans run on a real tmp_path image set; CLIP embedding is
monkeypatched to synthetic vectors so no model or GPU is involved.
"""
import pytest
from PySide6.QtTest import QTest as qt_test
from PySide6.QtWidgets import QLabel, QPushButton

from gui.src.components.dialogs import dataset_advisor_panel as panel_module
from gui.src.components.dialogs.dataset_advisor_panel import AdvisorPanel

pytestmark = pytest.mark.gui


def _img(path, size=(32, 32), color=(10, 20, 30)):
    from PIL import Image

    Image.new("RGB", size, color).save(path)
    return str(path)


def _caption(image_path, text):
    from pathlib import Path

    Path(image_path).with_suffix(".txt").write_text(text, encoding="utf-8")


def _wait_for(predicate, timeout_ms=8000):
    qt_test.qWait(0)
    elapsed = 0
    while not predicate() and elapsed < timeout_ms:
        qt_test.qWait(25)
        elapsed += 25
    return predicate()


def _texts(widget):
    labels = [w.text() for w in widget.cards_host.findChildren(QLabel)]
    buttons = [w.text() for w in widget.cards_host.findChildren(QPushButton)]
    return labels, buttons


def _button(widget, text):
    return next((w for w in widget.cards_host.findChildren(QPushButton) if w.text() == text), None)


@pytest.fixture
def panel(q_app):
    widget = AdvisorPanel()
    widget.set_hydra_available(True)
    yield widget
    widget.stop()
    widget.close()


class TestDeterministicScan:
    def test_clean_dataset_shows_no_issues(self, panel, tmp_path):
        paths = [_img(tmp_path / f"c{i}.png", color=(i, 20, 30)) for i in range(4)]
        for p in paths:
            _caption(p, "1girl, mychar")
        panel.set_images(paths, trigger="mychar")
        assert _wait_for(lambda: "4 images" in panel.summary_label.text())
        labels, _ = _texts(panel)
        assert any("No issues found" in text for text in labels)

    def test_duplicate_card_exclude_emits_all_but_first(self, panel, tmp_path):
        a = _img(tmp_path / "a.png", color=(99, 99, 99))
        b = _img(tmp_path / "b.png", color=(99, 99, 99))
        seen = []
        panel.exclude_requested.connect(seen.append)
        panel.set_images([a, b], trigger="")
        assert _wait_for(lambda: _button(panel, "Exclude 1 duplicate(s)") is not None)
        _button(panel, "Exclude 1 duplicate(s)").click()
        assert seen == [[b]]  # sorted order: a kept, b excluded

    def test_missing_captions_queues_hydra_override_and_chip_removes(self, panel, tmp_path):
        a = _img(tmp_path / "a.png")
        b = _img(tmp_path / "b.png", color=(1, 2, 3))
        panel.set_images([a, b], trigger="")
        button_name = "Queue Hydra override: pipeline.run_captioning=true"
        assert _wait_for(lambda: _button(panel, button_name) is not None)
        _button(panel, button_name).click()
        assert panel.hydra_overrides() == ["pipeline.run_captioning=true"]
        chip = lambda: next(  # noqa: E731
            (w for w in panel.overrides_row.findChildren(QPushButton)
             if w.text() == "pipeline.run_captioning=true ×"), None)
        assert _wait_for(lambda: chip() is not None)
        # card now shows the queued state, not a second button
        _, buttons = _texts(panel)
        assert "Queued ✓" in buttons
        chip().click()
        assert panel.hydra_overrides() == []

    def test_missing_captions_falls_back_to_review_tags_without_hydra(self, panel, tmp_path):
        panel.set_hydra_available(False)
        a = _img(tmp_path / "a.png")
        panel.set_images([a], trigger="")
        assert _wait_for(lambda: _button(panel, "Review Tags") is not None)
        requested = []
        panel.review_tags_requested.connect(lambda: requested.append(True))
        _button(panel, "Review Tags").click()
        assert requested == [True]

    def test_unreadable_card_show_selects_paths(self, panel, tmp_path):
        good = _img(tmp_path / "good.png")
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"garbage")
        seen = []
        panel.selection_requested.connect(seen.append)
        panel.set_images([good, str(bad)], trigger="")
        assert _wait_for(lambda: _button(panel, "Show") is not None)
        _button(panel, "Show").click()
        assert seen and set(seen[0]) == {str(bad)}

    def test_entanglement_card_has_no_button(self, panel, tmp_path):
        paths = []
        for i in range(10):
            p = _img(tmp_path / f"u{i}.png", color=(i, 1, 2))
            _caption(p, "1girl, mychar, school_uniform")
            paths.append(p)
        panel.set_images(paths, trigger="mychar")
        assert _wait_for(
            lambda: any("school_uniform" in t for t in _texts(panel)[0])
        )
        labels, buttons = _texts(panel)
        assert any("school_uniform" in t for t in labels)
        assert not any("school_uniform" in b for b in buttons)
        # composition tags are framing, not entanglement — kept quiet
        assert all("'1girl'" not in t for t in labels)


class TestClustering:
    def test_cluster_renders_diversity_findings(self, panel, tmp_path, monkeypatch):
        import numpy as np

        paths = [_img(tmp_path / f"v{i}.png", color=(i, 5, 6)) for i in range(12)]
        rng = np.random.default_rng(7)
        embeddings = {}
        for p in paths:
            v = rng.normal(size=16).astype(np.float32)
            embeddings[p] = v / np.linalg.norm(v)
        base = rng.normal(size=16).astype(np.float32)
        base /= np.linalg.norm(base)
        embeddings[paths[0]] = base
        embeddings[paths[1]] = base.copy()
        embeddings[paths[2]] = base * 0.999 + np.full(16, 0.001, dtype=np.float32)
        monkeypatch.setattr(panel_module, "embed_paths", lambda *a, **k: embeddings)

        panel.set_images(paths, trigger="")
        assert _wait_for(lambda: "images" in panel.summary_label.text())
        panel.cluster_btn.click()
        assert _wait_for(
            lambda: any("Near-duplicate cluster" in t for t in _texts(panel)[0]),
            timeout_ms=15000,
        )
        labels, buttons = _texts(panel)
        cluster_card = next(t for t in labels if "Near-duplicate cluster" in t)
        assert "3" in cluster_card

    def test_training_guard_disables_cluster_button(self, panel):
        panel.set_training_guard(lambda: True)
        assert not panel.cluster_btn.isEnabled()
        panel.set_training_guard(lambda: False)
        assert panel.cluster_btn.isEnabled()


class TestExclusionChip:
    def test_restore_emits_signal(self, panel):
        seen = []
        panel.restore_requested.connect(lambda: seen.append(True))
        panel.set_exclusion_count(2)
        assert panel.exclusions_row.isVisibleTo(panel)
        assert "2 file(s) excluded" in panel.exclusions_label.text()
        restore = next(
            w for w in panel.exclusions_row.findChildren(QPushButton) if w.text() == "Restore"
        )
        restore.click()
        assert seen == [True]
