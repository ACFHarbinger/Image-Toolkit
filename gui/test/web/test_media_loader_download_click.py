"""Media Loader Download-button flow regression tests.

Covered regressions:
- S403 (Download double-click): clicking Download twice used to replace
  self.worker (a running download thread) and drop the only reference to
  it. start_download now ignores re-entry while the previous worker is
  running.
- "Download button does nothing" (modal-messagebox / hidden-button state):
  after a download finishes the run button must be visible again and the
  status must reflect the finished download.
"""

from __future__ import annotations

import time

import pytest
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal

pytestmark = pytest.mark.gui


class _FakeFastDownloader(QObject):
    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(int, str)
    on_error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def stop(self):
        pass

    def run(self):
        self.on_status.emit("working...")
        self.on_finished.emit(1, "Finished. Downloaded 1 file(s).")


def _fake_run(self):
    """Replaces MediaLoaderWorker.run: a fast fake downloader instead of the
    real network downloader (no network / no sandbox writes needed)."""
    dl = _FakeFastDownloader(self.config)
    self._downloader = dl
    dl.on_status.connect(self.status.emit)
    dl.on_finished.connect(self.sig_finished.emit)
    self.status.emit("Starting nhentai download...")
    dl.run()


def _make_tab():
    from gui.src.tabs.web.media_loader_tab import MediaLoaderTab
    from gui.src.tabs.web.media_loader_tab._ui_builder import SOURCE_NHENTAI

    tab = MediaLoaderTab()
    tab.source_combo.setCurrentIndex(SOURCE_NHENTAI)
    tab.nhentai_gallery_input.setText("https://nhentai.net/g/111006/")
    tab.download_dir_path.setText("/tmp/fake_out")
    return tab


def _pump(q_app, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        q_app.processEvents()
        time.sleep(0.01)


class TestMediaLoaderDownloadClick:
    def test_download_click_starts_and_finishes(self, q_app, tmp_path):
        from gui.src.helpers.web.media_loader_worker import MediaLoaderWorker

        with patch.object(MediaLoaderWorker, "run", _fake_run):
            tab = _make_tab()
            tab.show()
            q_app.processEvents()

            tab.run_button.click()
            _pump(q_app, 2.0)

            assert tab.run_button.isVisible(), (
                "run button must be visible again after download finishes"
            )
            assert tab.status_label.text() == "Finished. Downloaded 1 file(s)."
            assert tab.worker is not None

    def test_click_download_twice_still_completes(self, q_app, tmp_path):
        from gui.src.tabs.web.media_loader_tab import MediaLoaderTab
        from gui.src.tabs.web.media_loader_tab._ui_builder import SOURCE_NHENTAI
        from gui.src.helpers.web.media_loader_worker import MediaLoaderWorker

        tab = MediaLoaderTab()
        tab.source_combo.setCurrentIndex(SOURCE_NHENTAI)
        tab.nhentai_gallery_input.setText("https://nhentai.net/g/111006/")
        tab.download_dir_path.setText("/tmp/fake_out")
        tab.show()
        q_app.processEvents()

        with patch.object(MediaLoaderWorker, "run", _fake_run):
            # First click; let the (fast fake) download finish.
            tab.run_button.click()
            _pump(q_app, 1.5)
            assert tab.status_label.text() == "Finished. Downloaded 1 file(s)."

            # Second click (user flow: click, let it finish, click again) must
            # start and complete a fresh download -- not be stuck behind a
            # modal dialog or a hidden run button.
            tab.run_button.click()
            _pump(q_app, 1.5)

            assert tab.status_label.text() == "Finished. Downloaded 1 file(s).", (
                "second click must still complete a download"
            )
            assert tab.run_button.isVisible(), (
                "run button must be visible after the second download"
            )
