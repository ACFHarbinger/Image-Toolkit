"""Thread ownership must outlive result delivery and deleted UI owners."""
import threading

import pytest
from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import _retained, retain_until_stopped
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest as qt_test

pytestmark = pytest.mark.gui


def test_payload_does_not_release_live_thread(q_app):
    release = threading.Event()
    delivered = threading.Event()

    class Worker(BaseQThreadWorker):
        def _execute(self):
            return None

        def run(self):
            self.finished.emit(None)
            delivered.set()
            release.wait(3)

    worker = Worker()
    worker.start()
    retain_until_stopped(worker)
    try:
        assert delivered.wait(1)
        qt_test.qWait(60)
        assert id(worker) in _retained
        assert worker.isRunning()
    finally:
        release.set()
        assert worker.wait(1000)
    qt_test.qWait(60)
    assert id(worker) not in _retained


def test_review_worker_survives_panel_deletion(q_app):
    from gui.src.components.dialogs.tag_review_panel import TagReviewPanel
    from gui.src.helpers.models.tag_review_worker import TagReviewWorker

    release = threading.Event()

    class Worker(TagReviewWorker):
        def _execute(self):
            release.wait(3)

    worker = Worker([])
    panel = TagReviewPanel()
    panel._worker = worker
    worker.sig_progress.connect(panel._on_progress)
    worker.sig_result.connect(panel._on_result)
    worker.sig_item_error.connect(panel._on_item_error)
    worker.finished.connect(panel._on_tagging_finished)
    worker.error.connect(panel._on_error)
    worker.start()
    try:
        panel.stop_review()
        panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_test.qWait(40)
        assert id(worker) in _retained
    finally:
        release.set()
        assert worker.wait(1000)
    qt_test.qWait(60)
    assert id(worker) not in _retained


def test_workspace_defers_deletion_until_training_returns(q_app):
    from gui.src.modules.dl_workspace import DeepLearningWorkspaceHandle

    class Host:
        ready = False
        deleted = False

        def prepare_dispose(self):
            pass

        def disposal_ready(self):
            return self.ready

        def hide(self):
            pass

        def deleteLater(self):
            self.deleted = True

    host = Host()
    DeepLearningWorkspaceHandle(host).dispose()
    qt_test.qWait(60)
    assert not host.deleted
    host.ready = True
    qt_test.qWait(60)
    assert host.deleted


def test_replaced_dataset_worker_is_retained_and_cleans_unused_result(q_app, tmp_path, monkeypatch):
    from gui.src.tabs.models.delta.lora_train_tab import ImportedDataset, LoRATrainTab

    release = threading.Event()
    entered = threading.Event()
    old_dir = tmp_path / "old-stage"
    new_dir = tmp_path / "new-stage"
    old_dir.mkdir()
    new_dir.mkdir()

    def resolve(paths, **kwargs):
        if paths == ("old",):
            entered.set()
            release.wait(3)
            return ImportedDataset(str(old_dir), (), "selection", True)
        return ImportedDataset(str(new_dir), (), "selection", True)

    monkeypatch.setattr("gui.src.tabs.models.delta.lora_train_tab.resolve_imported_dataset", resolve)
    tab = LoRATrainTab()
    tab.apply_imported_paths(("old",))
    old = tab._dataset_worker
    try:
        assert entered.wait(1)
        tab.apply_imported_paths(("new",))
        new = tab._dataset_worker
        assert new.wait(1000)
        q_app.processEvents()
        assert id(old) in _retained
        assert tab.data_dir_edit.text() == str(new_dir)
    finally:
        release.set()
        assert old.wait(1000)
    for _ in range(30):
        qt_test.qWait(10)
        if not old_dir.exists():
            break
    assert not old_dir.exists()
    assert new_dir.exists()
    tab._clear_staging()
    tab.deleteLater()
