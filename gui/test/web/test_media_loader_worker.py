"""Tests for MediaLoaderWorker: source dispatch and signal forwarding.

Regression coverage for the app crash triggered by clicking Download on the
nhentai source in the Media Loader tab (SIGSEGV/heap corruption via
``QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread``). The downloader QObject must be constructed on the GUI
thread; only ``downloader.run()`` may run on a plain ``threading.Thread``.
These tests exercise the worker's dispatch/forwarding logic only (the real
downloaders have their own unit tests in ``backend/test/web/``), using a
fake downloader with real Observables so emissions actually forward through
the worker's QtEventBridges.
"""

import threading
from unittest.mock import patch

from backend.src.events import Observable

from gui.src.helpers.web.media_loader_worker import MediaLoaderWorker


def _seen_config_capture(seen: dict, config):
    """Fake downloader factory recording the config it was built with."""
    fake = _FakeDownloader(config)
    seen["config"] = config
    return fake


class _FakeDownloader:
    """Mirrors the real backend downloaders' event surface (issue #529)."""

    def __init__(self, config):
        self.config = config
        self.stopped = False
        self.ran = False
        self.on_status: Observable[str] = Observable()
        self.on_image_saved: Observable[str] = Observable()
        self.on_finished: Observable[tuple[int, str]] = Observable()
        self.on_error: Observable[str] = Observable()

    def stop(self):
        self.stopped = True

    def run(self):
        self.ran = True
        self.on_status.publish("working...")
        self.on_image_saved.publish("/tmp/fake.jpg")
        self.on_finished.publish((1, "Finished. Downloaded 1 file(s)."))


def _run_worker(q_app, source, config, downloader_cls, patch_target):
    with patch(patch_target, downloader_cls):
        worker = MediaLoaderWorker(source, config)

        statuses = []
        saved = []
        finished = []
        errors = []
        worker.status.connect(statuses.append)
        worker.media_saved.connect(saved.append)
        worker.sig_finished.connect(lambda count, msg: finished.append((count, msg)))
        worker.error.connect(errors.append)

        worker.run()
        # Bridge delivery is queued (Qt.QueuedConnection) even on the test
        # thread — pump the loop so forwarded events land before asserting.
        q_app.processEvents()

        return worker, statuses, saved, finished, errors


class _NeverFinishingWorker(MediaLoaderWorker):
    """A MediaLoaderWorker that stays running until stopped, so a test can
    hold it as tab.worker and verify start_download does not replace it."""

    def __init__(self, source, config):
        super().__init__(source, config)
        self._stop = False

    def start(self):
        # Skip downloader construction: this stub never downloads.
        if self.isRunning():
            return
        self._thread = threading.Thread(
            target=self.run, name="media-loader-test", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            import time

            time.sleep(0.01)


class TestMediaLoaderWorkerDispatch:
    def test_reddit_source_constructs_reddit_downloader(self, q_app, tmp_path):
        config = {"source": "EarthPorn", "download_dir": str(tmp_path)}
        worker, statuses, saved, finished, errors = _run_worker(
            q_app, "reddit", config, _FakeDownloader,
            "gui.src.helpers.web.media_loader_worker.RedditDownloader",
        )

        # The downloader is created on the GUI thread (this test calls
        # run() synchronously) and kept there -- destroying it from the
        # worker thread is the crash. Events still forward via the bridges.
        assert "working..." in statuses
        assert saved == ["/tmp/fake.jpg"]
        assert finished == [(1, "Finished. Downloaded 1 file(s).")]
        assert errors == []
        assert worker._downloader is not None

    def test_nhentai_source_constructs_nhentai_downloader(self, q_app, tmp_path):
        config = {"gallery": "111006", "download_dir": str(tmp_path)}
        worker, statuses, saved, finished, errors = _run_worker(
            q_app, "nhentai", config, _FakeDownloader,
            "gui.src.helpers.web.media_loader_worker.NhentaiDownloader",
        )

        assert finished == [(1, "Finished. Downloaded 1 file(s).")]
        assert worker._downloader is not None

    def test_unknown_source_emits_error_without_constructing_anything(self, q_app, tmp_path):
        worker = MediaLoaderWorker("unknown-source", {"download_dir": str(tmp_path)})
        errors = []
        worker.error.connect(errors.append)

        worker.run()

        assert worker._downloader is None
        assert len(errors) == 1
        assert "Unknown media source" in errors[0]

    def test_cancel_forwards_to_downloader_stop(self, q_app, tmp_path):
        config = {"source": "EarthPorn", "download_dir": str(tmp_path)}
        with patch(
            "gui.src.helpers.web.media_loader_worker.RedditDownloader", _FakeDownloader
        ):
            worker = MediaLoaderWorker("reddit", config)
            # cancel() before start()/run() must not raise if the
            # downloader has not been constructed yet.
            worker.cancel()
            assert worker._downloader is None

            worker._downloader = _FakeDownloader(config)
            worker.cancel()
            assert worker._downloader.stopped

class TestOnExistsPassThrough:
    """The dropdown selection must reach the downloader config unchanged."""

    def test_worker_receives_on_exists_in_config(self, q_app, tmp_path):
        config = {
            "source": "EarthPorn",
            "download_dir": str(tmp_path),
            "on_exists": "rename",
        }
        # Capture the config the downloader was constructed with.
        seen = {}
        with patch(
            "gui.src.helpers.web.media_loader_worker.RedditDownloader",
            lambda cfg: _seen_config_capture(seen, cfg),
        ):
            worker = MediaLoaderWorker("reddit", config)
            worker.run()
        assert seen["config"]["on_exists"] == "rename"

    def test_worker_defaults_on_exists_to_overwrite(self, q_app, tmp_path):
        config = {"source": "EarthPorn", "download_dir": str(tmp_path)}
        seen = {}
        with patch(
            "gui.src.helpers.web.media_loader_worker.RedditDownloader",
            lambda cfg: _seen_config_capture(seen, cfg),
        ):
            worker = MediaLoaderWorker("reddit", config)
            worker.run()
        assert seen["config"].get("on_exists") is None

    def test_tab_builds_dropdown_with_three_policies(self, q_app):
        """MediaLoaderTab exposes the existing-file dropdown with the three
        policy values the backend understands."""
        from gui.src.tabs.web.media_loader_tab import MediaLoaderTab

        tab = MediaLoaderTab()
        assert tab.on_exists_combo.count() == 3
        values = [
            tab.on_exists_combo.itemData(i) for i in range(tab.on_exists_combo.count())
        ]
        assert values == ["overwrite", "skip", "rename"]

class TestDownloaderThreadAffinity:
    """The downloader QObject must be constructed on the GUI thread.

    Constructing it inside the worker thread is the QSocketNotifier /
    fd-reuse crash (Dummy-N + requests sockets + live JVM).
    """

    def test_start_constructs_downloader_on_caller_thread(self, q_app, tmp_path):
        constructed_on = {}

        class _RecordingDownloader(_FakeDownloader):
            def __init__(self, config):
                super().__init__(config)
                constructed_on["ctor"] = threading.get_ident()
                # pyrefly: ignore [unsupported-operation]
                constructed_on["run"] = None

            def run(self):
                constructed_on["run"] = threading.get_ident()
                super().run()

        config = {"gallery": "111006", "download_dir": str(tmp_path)}
        main_ident = threading.get_ident()
        with patch(
            "gui.src.helpers.web.media_loader_worker.NhentaiDownloader",
            _RecordingDownloader,
        ):
            worker = MediaLoaderWorker("nhentai", config)
            worker.start()
            assert worker.wait(2000)
        assert constructed_on["ctor"] == main_ident
        assert constructed_on["run"] is not None
        assert constructed_on["run"] != main_ident


class TestStartDownloadReentryGuard:
    """Clicking Download while a previous worker is still alive must not
    replace it: the second start_download would drop the only reference
    to a running download thread."""

    def test_start_download_ignored_while_worker_running(self, q_app):
        from gui.src.tabs.web.media_loader_tab import MediaLoaderTab
        from gui.src.tabs.web.media_loader_tab._ui_builder import SOURCE_NHENTAI

        tab = MediaLoaderTab()
        tab.source_combo.setCurrentIndex(SOURCE_NHENTAI)
        tab.download_dir_path.setText("/tmp/fake_out")
        tab.nhentai_gallery_input.setText("https://nhentai.net/g/111006/")

        # A worker that never finishes: isRunning() must stay True so the
        # guard sees an in-flight download.
        worker = _NeverFinishingWorker("nhentai", {"download_dir": "/tmp"})
        tab.worker = worker
        worker.start()

        try:
            tab.start_download()
            assert tab.worker is worker, (
                "start_download must NOT replace a still-running worker "
                "(old QThread + worker-thread downloader would be GC'd "
                "cross-thread on the next click)"
            )
        finally:
            worker.stop()
            worker.wait(2000)
            if tab.worker is not None and tab.worker is not worker:
                tab.worker.stop()
                tab.worker.wait(2000)
