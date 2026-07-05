from unittest.mock import MagicMock, patch

import numpy as np
from gui.src.helpers.image.batch_image_loader_worker import BatchImageLoaderWorker
from gui.src.helpers.image.image_loader_worker import ImageLoaderWorker
from gui.src.helpers.image.image_scan_worker import ImageScannerWorker

# --- ImageLoaderWorker Tests ---


class TestImageLoaderWorker:
    def test_run(self, q_app):
        with patch("gui.src.helpers.image.image_loader_worker.QImage") as MockQImage:
            mock_inst = MagicMock()
            MockQImage.return_value = mock_inst
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
        with patch("gui.src.helpers.image.image_loader_worker.QImage") as MockQImage:
            mock_inst = MagicMock()
            MockQImage.return_value = mock_inst
            mock_inst.isNull.return_value = True  # Load failed

            worker = ImageLoaderWorker("/tmp/bad.jpg", 100)

            results = []
            worker.signals.result.connect(lambda p, px: results.append((p, px)))

            worker.run()

            assert len(results) == 1
            assert results[0][0] == "/tmp/bad.jpg"


# --- ImageScannerWorker Tests ---


class TestImageScannerWorker:
    def test_run_scan(self, q_app, tmp_path):
        # Create dummy structure
        d = tmp_path / "images"
        d.mkdir()
        (d / "test1.jpg").touch()
        (d / "test2.png").touch()
        (d / "ignore.txt").touch()

        # Force HAS_NATIVE_IMAGING to False to test fallback python logic
        with patch(
            "gui.src.helpers.image.image_scan_worker.HAS_NATIVE_IMAGING", False
        ):
            worker = ImageScannerWorker([str(d)])

            finished_signals = []
            worker.scan_finished.connect(lambda r: finished_signals.append(r))

            worker.run_scan()

            assert len(finished_signals) == 1
            found = finished_signals[0]
            assert len(found) == 2
            assert any("test1.jpg" in f for f in found)

    def test_error(self, q_app):
        worker = ImageScannerWorker([])

        error_signals = []
        worker.scan_error.connect(lambda e: error_signals.append(e))

        worker.run_scan()

        assert len(error_signals) == 1
        assert "No valid directories" in error_signals[0]


class TestBatchImageLoaderWorker:
    def test_run_fallback(self, q_app):
        # Force fallback by mocking HAS_NATIVE_IMAGING = False
        with patch(
            "gui.src.helpers.image.batch_image_loader_worker.HAS_NATIVE_IMAGING", False
        ), patch(
            "gui.src.helpers.image.batch_image_loader_worker.QImage"
        ) as MockQImage:
            mock_inst = MagicMock()
            MockQImage.return_value = mock_inst
            mock_inst.isNull.return_value = False
            mock_inst.scaled.return_value = MagicMock()

            paths = ["/tmp/1.jpg", "/tmp/2.jpg"]
            worker = BatchImageLoaderWorker(paths, 100)

            results = []
            # batch_result emits list of (path, QImage)
            worker.signals.batch_result.connect(lambda res: results.append(res))

            worker.run()

            assert len(results) == 1
            batch = results[0]
            assert len(batch) == 2
            assert batch[0][0] == "/tmp/1.jpg"
            assert batch[1][0] == "/tmp/2.jpg"

    def test_run_native(self, q_app):
        # Test native C++ path
        with patch(
            "gui.src.helpers.image.batch_image_loader_worker.HAS_NATIVE_IMAGING", True
        ), patch(
            "gui.src.helpers.image.batch_image_loader_worker.base"
        ) as mock_base:
            mock_arr = np.zeros((10, 10, 3), dtype=np.uint8)
            mock_base.load_image_batch.return_value = [("/tmp/mp.jpg", mock_arr, "")]

            paths = ["/tmp/mp.jpg"]
            worker = BatchImageLoaderWorker(paths, 100)

            results = []
            worker.signals.batch_result.connect(lambda res: results.append(res))

            worker.run()

            # Native fast path passes rgb=True and the disk cache dir
            from backend.src.constants import THUMBNAIL_CACHE_DIR

            mock_base.load_image_batch.assert_called_once_with(
                paths, 100, 100, True, True, str(THUMBNAIL_CACHE_DIR)
            )
            assert len(results) == 1
            batch = results[0]
            assert len(batch) == 1
            assert batch[0][0] == "/tmp/mp.jpg"
            assert not batch[0][1].isNull()
