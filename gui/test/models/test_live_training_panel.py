"""#742: live training panel. The tail is fed by ingest; no training process starts."""
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import QProgressBar, QPushButton, QWidget

from gui.src.tabs.models.delta.live_training_panel import LiveTrainingPanel
from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    from unittest.mock import patch

    with patch("gui.src.tabs.models.delta.lora_train_tab.QMessageBox"):
        yield


def _png(path) -> None:
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    image.save(str(path))


def test_ingest_fills_epoch_sparkline_and_scrub_highlight(tmp_path, q_app):
    sample = tmp_path / "samples"
    sample.mkdir()
    _png(sample / "step-000010.png")
    _png(sample / "step-000020.png")
    panel = LiveTrainingPanel()
    try:
        panel.begin(5)
        panel.follow(str(tmp_path))
        panel.ingest(
            [
                {"step": 1, "epoch": 1, "loss": 0.9},
                {"step": 10, "epoch": 2, "loss": 0.4, "sample": "samples/step-000010.png"},
                {"step": 20, "epoch": 2, "loss": 0.2, "sample": "samples/step-000020.png"},
                {"step": 21, "sample": "../outside.png"},
            ]
        )
        q_app.processEvents()

        epoch = panel.findChild(QProgressBar, "live_training_epoch")
        spark = panel.findChild(QWidget, "live_training_sparkline")
        assert epoch.value() == 3
        assert epoch.maximum() == 5
        assert "loss" in spark.text()
        assert panel.findChild(QPushButton, "checkpoint_10") is not None
        assert panel.findChild(QPushButton, "checkpoint_21") is None

        curve = panel.findChild(QWidget, "live_training_curve")
        curve.resize(400, 120)
        curve.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(399, 10),
                QPointF(399, 10),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        assert panel.findChild(QPushButton, "checkpoint_20").isChecked()
        assert panel.findChild(QWidget, "live_training_compare") is not None
    finally:
        panel.shutdown()


def test_train_tab_hosts_the_panel_and_resets_it_when_training_starts(tab_factory, monkeypatch, q_app):
    tab = tab_factory()
    assert tab.findChild(QWidget, "live_training_panel") is not None
    monkeypatch.setattr(
        "gui.src.tabs.models.delta.lora_train_tab.try_admit",
        lambda _owner, **_kw: "GPU admission is held by other.",
    )
    tab.widgets["epochs"].setValue(7)
    tab.start_training_thread()
    tab._training_thread.join(timeout=2)
    # Deliver the queued error dialog while QMessageBox is still patched.
    q_app.processEvents()
    epoch = tab.findChild(QProgressBar, "live_training_epoch")
    assert epoch.maximum() == 7
    assert epoch.value() == 0


def test_run_training_announces_the_run_directory(tab_factory, tmp_path, monkeypatch):
    tab = tab_factory()
    seen = []
    tab.run_directory_ready.connect(seen.append)
    monkeypatch.setattr("gui.src.tabs.models.delta.lora_train_tab.try_admit", lambda _owner, **_kw: None)
    monkeypatch.setattr("gui.src.tabs.models.delta.lora_train_tab.gpu_lease.release", lambda *_a, **_k: None)
    monkeypatch.setattr(tab, "_create_run_record", lambda *_a, **_k: tmp_path)
    monkeypatch.setattr(tab, "_run_training_admitted", lambda *_a, **_k: None)
    tab.run_training({}, "/data", "model", 4, "prompt", "output")
    assert seen == [str(tmp_path)]
    tab._live_panel.shutdown()


@pytest.fixture
def tab_factory():
    def _make():
        return LoRATrainTab()

    return _make


def test_thumbnail_survives_next_sample_and_old_run_results_are_ignored(tmp_path, q_app):
    import time
    panel = LiveTrainingPanel()
    try:
        panel.begin(2)
        panel.follow(str(tmp_path))
        _png(tmp_path / "one.png")
        _png(tmp_path / "two.png")
        panel.ingest([{"step": 1, "sample": "one.png"}])
        deadline = time.monotonic() + 2
        while 1 not in panel._icons and time.monotonic() < deadline:
            q_app.processEvents()
            time.sleep(.01)
        assert 1 in panel._icons
        panel.ingest([{"step": 2, "sample": "two.png"}])
        assert not panel.findChild(QPushButton, "checkpoint_1").icon().isNull()
        old_generation = panel._generation
        panel.begin(2)
        panel._apply_thumb(old_generation, 1, b"stale")
        assert panel._icons == {}
    finally:
        panel.shutdown()
