from unittest.mock import MagicMock, patch

from gui.src.helpers.image.image_loader_worker import (
    ImageLoaderWorker,
    BatchImageLoaderWorker,
)
from gui.src.helpers.image.image_scan_worker import ImageScannerWorker

# --- ImageLoaderWorker Tests ---


class TestImageLoaderWorker:
    def test_run(self, q_app):
        # We can test the actual logic or mocking QPixmap if needed.
        # Since we shouldn't rely on existing files, let's patch QPixmap

        with patch("gui.src.helpers.image.image_loader_worker.QPixmap") as MockPixmap:
            # Setup mock pixmap behavior
            mock_inst = MagicMock()
            MockPixmap.return_value = mock_inst
            mock_inst.isNull.return_value = False
            mock_inst.scaled.return_value = MagicMock()

            worker = ImageLoaderWorker("/tmp/fake.jpg", 100)

            # Catch signals
            results = []
            worker.signals.result.connect(lambda p, px: results.append((p, px)))

            worker.run()

            assert len(results) == 1
            assert results[0][0] == "/tmp/fake.jpg"
            mock_inst.scaled.assert_called()

    def test_run_failure(self, q_app):
        with patch("gui.src.helpers.image.image_loader_worker.QPixmap") as MockPixmap:
            mock_inst = MagicMock()
            MockPixmap.return_value = mock_inst
            mock_inst.isNull.return_value = True  # Load failed

            worker = ImageLoaderWorker("/tmp/bad.jpg", 100)

            results = []
            worker.signals.result.connect(lambda p, px: results.append((p, px)))

            worker.run()

            assert len(results) == 1
            assert results[0][0] == "/tmp/bad.jpg"
            # Should return a (likely null) pixmap, but we just check signal emitted


# --- ImageScannerWorker Tests ---


class TestImageScannerWorker:
    def test_run_scan(self, q_app, tmp_path):
        # Create dummy structure
        d = tmp_path / "images"
        d.mkdir()
        (d / "test1.jpg").touch()
        (d / "test2.png").touch()
        (d / "ignore.txt").touch()

        worker = ImageScannerWorker([str(d)])

        finished_signals = []
        worker.scan_finished.connect(lambda r: finished_signals.append(r))

        worker.run_scan()

        assert len(finished_signals) == 1
        found = finished_signals[0]
        assert len(found) == 2
        assert any("test1.jpg" in f for f in found)

    def test_error(self, q_app):
        # Test error signal by passing None or invalid types that might cause crash if not handled,
        # or mock os.scandir to raise
        worker = ImageScannerWorker([])

        error_signals = []
        worker.scan_error.connect(lambda e: error_signals.append(e))

        worker.run_scan()

        assert len(error_signals) == 1
        assert "No valid directories" in error_signals[0]
        assert len(error_signals) == 1
        assert "No valid directories" in error_signals[0]


class TestBatchImageLoaderWorker:
    def test_run_fallback(self, q_app):
        # Force fallback by mocking HAS_NATIVE_IMAGING = False
        with patch(
            "gui.src.helpers.image.image_loader_worker.HAS_NATIVE_IMAGING", False
        ):
            with patch(
                "gui.src.helpers.image.image_loader_worker.QPixmap"
            ) as MockPixmap:
                mock_inst = MagicMock()
                MockPixmap.return_value = mock_inst
                mock_inst.isNull.return_value = False
                mock_inst.scaled.return_value = MagicMock()

                paths = ["/tmp/1.jpg", "/tmp/2.jpg"]
                worker = BatchImageLoaderWorker(paths, 100)

                results = []
                # batch_result emits list of (path, pixmap)
                worker.signals.batch_result.connect(lambda res: results.append(res))

                worker.run()

                assert len(results) == 1
                batch = results[0]
                assert len(batch) == 2
                assert batch[0][0] == "/tmp/1.jpg"
                assert batch[1][0] == "/tmp/2.jpg"

    def test_run_multiprocessing(self, q_app):
        # Test executor path
        with patch(
            "gui.src.helpers.image.image_loader_worker.HAS_NATIVE_IMAGING", True
        ):
            # Mock executor
            mock_executor = MagicMock()
            mock_future = MagicMock()
            mock_executor.submit.return_value = mock_future

            # Fake return from process_image_batch: (path, buffer, w, h)
            # Buffer must be bytes
            mock_future.result.return_value = [("/tmp/mp.jpg", b"fakebytes", 10, 10)]

            paths = ["/tmp/mp.jpg"]
            worker = BatchImageLoaderWorker(paths, 100, executor=mock_executor)

            results = []
            worker.signals.batch_result.connect(lambda res: results.append(res))

            with patch(
                "gui.src.helpers.image.image_loader_worker.QImage"
            ) as MockQImage:
                with patch(
                    "gui.src.helpers.image.image_loader_worker.QPixmap"
                ) as MockQPixmap:
                    worker.run()

                    mock_executor.submit.assert_called()
                    assert len(results) == 1
                    batch = results[0]
                    assert len(batch) == 1
                    assert batch[0][0] == "/tmp/mp.jpg"
