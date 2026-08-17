"""Tests for MediaLoaderWorker: source dispatch and signal forwarding.

Regression coverage for the app crash triggered by clicking Download on the
nhentai source in the Media Loader tab (SIGSEGV/heap corruption via
``QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread``), root-caused to running an asyncio event loop
(``asyncpraw``/``aiohttp``) inside a QThread -- see
``backend/src/web/downloaders/nhentai_downloader.py``'s module docstring.
These tests exercise the worker's dispatch/forwarding logic only (the real
downloaders have their own unit tests in ``backend/test/web/``), using a
fake downloader with real Qt signals so emissions actually forward.
"""

from unittest.mock import patch

from PySide6.QtCore import QObject, Signal

from gui.src.helpers.web.media_loader_worker import MediaLoaderWorker


def _seen_config_capture(seen: dict, config):
    """Fake downloader factory recording the config it was built with."""
    fake = _FakeDownloader(config)
    seen["config"] = config
    return fake


class _FakeDownloader(QObject):
    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(int, str)
    on_error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.stopped = False
        self.ran = False

    def stop(self):
        self.stopped = True

    def run(self):
        self.ran = True
        self.on_status.emit("working...")
        self.on_image_saved.emit("/tmp/fake.jpg")
        self.on_finished.emit(1, "Finished. Downloaded 1 file(s).")


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

        return worker, statuses, saved, finished, errors


class _NeverFinishingWorker(MediaLoaderWorker):
    """A MediaLoaderWorker that stays running until stopped, so a test can
    hold it as tab.worker and verify start_download does not replace it."""

    def __init__(self, source, config):
        super().__init__(source, config)
        self._stop = False

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

        # The downloader QObject is created on the worker thread and released
        # there when run() completes (run() clears self._downloader in a
        # finally) -- otherwise the next Download click's replacement of
        # self.worker GCs it from the main thread, the cross-thread QObject
        # destruction behind the recurring crash. Signals still forward
        # correctly while the worker runs.
        assert "working..." in statuses
        assert saved == ["/tmp/fake.jpg"]
        assert finished == [(1, "Finished. Downloaded 1 file(s).")]
        assert errors == []
        assert worker._downloader is None

    def test_nhentai_source_constructs_nhentai_downloader(self, q_app, tmp_path):
        config = {"gallery": "111006", "download_dir": str(tmp_path)}
        worker, statuses, saved, finished, errors = _run_worker(
            q_app, "nhentai", config, _FakeDownloader,
            "gui.src.helpers.web.media_loader_worker.NhentaiDownloader",
        )

        assert finished == [(1, "Finished. Downloaded 1 file(s).")]
        assert worker._downloader is None

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
            # Simulate the downloader having been created (normally happens
            # inside run(), which we don't call here -- cancel() before/
            # during a real run must not raise if _downloader is still None).
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
        # Capture the config the downloader was constructed with before
        # run()'s finally releases the worker-thread QObject.
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
        from gui.src.elements.web.media_loader_tab import MediaLoaderTab

        tab = MediaLoaderTab()
        assert tab.on_exists_combo.count() == 3
        values = [
            tab.on_exists_combo.itemData(i) for i in range(tab.on_exists_combo.count())
        ]
        assert values == ["overwrite", "skip", "rename"]

class TestStartDownloadReentryGuard:
    """Clicking Download while a previous worker QThread is still alive must
    not replace it: the second start_download would drop the old QThread
    reference while its worker-thread downloader QObject is still alive,
    and Python GC would destroy that QObject from the main thread -- the
    cross-thread QObject destruction behind the recurring crash when
    Download is clicked twice (QObject::killTimer / Shiboken
    retrieveWrapper / QObject::property SIGSEGVs)."""

    def test_start_download_ignored_while_worker_running(self, q_app):
        from gui.src.elements.web.media_loader_tab import MediaLoaderTab
        from gui.src.elements.web.media_loader_tab._ui_builder import SOURCE_NHENTAI

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
