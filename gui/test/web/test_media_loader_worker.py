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

from gui.src.helpers.web.media_loader_worker import MediaLoaderWorker
from PySide6.QtCore import QObject, Signal


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


class TestMediaLoaderWorkerDispatch:
    def test_reddit_source_constructs_reddit_downloader(self, q_app, tmp_path):
        config = {"source": "EarthPorn", "download_dir": str(tmp_path)}
        worker, statuses, saved, finished, errors = _run_worker(
            q_app, "reddit", config, _FakeDownloader,
            "gui.src.helpers.web.media_loader_worker.RedditDownloader",
        )

        assert worker._downloader.ran
        assert "working..." in statuses
        assert saved == ["/tmp/fake.jpg"]
        assert finished == [(1, "Finished. Downloaded 1 file(s).")]
        assert errors == []

    def test_nhentai_source_constructs_nhentai_downloader(self, q_app, tmp_path):
        config = {"gallery": "111006", "download_dir": str(tmp_path)}
        worker, statuses, saved, finished, errors = _run_worker(
            q_app, "nhentai", config, _FakeDownloader,
            "gui.src.helpers.web.media_loader_worker.NhentaiDownloader",
        )

        assert worker._downloader.ran
        assert finished == [(1, "Finished. Downloaded 1 file(s).")]

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
