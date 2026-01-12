from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure mocks are in place (should be handled by conftest, but explicit check or re-import is safe)
import cv2
from PIL import Image

# Import the tasks
from gui.src.helpers.core.tasks.orb_task import OrbTask
from gui.src.helpers.core.tasks.phask_task import PhashTask
from gui.src.helpers.core.tasks.sift_task import SiftTask
from gui.src.helpers.core.tasks.sn_task import SiameseTask
from gui.src.helpers.core.tasks.ssim_task import SsimTask
from gui.src.helpers.core.tasks.scan_signals import ScanSignals

# Note: backend modules are mocked in conftest.py, so we can mock the Loader class return
from backend.src.models.siamese_network import SiameseModelLoader


class TestCoreHelperTasks:

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """
        Setup common mocks for all tests.
        """
        self.mock_image_open = patch("PIL.Image.open").start()
        # Create a mock image that supports convert and resize
        self.mock_pil_image = MagicMock()
        self.mock_image_open.return_value = self.mock_pil_image
        self.mock_pil_image.convert.return_value = self.mock_pil_image
        self.mock_pil_image.resize.return_value = self.mock_pil_image
        # Allow context manager for PhashTask
        self.mock_image_open.return_value.__enter__.return_value = self.mock_pil_image

        # Mock numpy array creation from image
        self.mock_np_array = patch("numpy.array").start()
        self.mock_np_array.return_value = np.zeros((100, 100), dtype=np.uint8)

        yield

        patch.stopall()

    def test_scan_signals(self):
        """Test ScanSignals initialization"""
        signals = ScanSignals()
        assert signals is not None
        # Verify signals are present
        assert hasattr(signals, "result")
        assert hasattr(signals, "error")

    def test_orb_task_success(self):
        """Test OrbTask successfully computes descriptors"""
        path = "/tmp/test_image.jpg"
        task = OrbTask(path)

        # Mock signals
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        # Mock cv2 ORB
        mock_orb_detector = MagicMock()
        # Return keypoints (dummy) and descriptors (dummy array)
        # Descriptors must be > 10 items to pass the check
        dummy_des = np.ones((15, 32), dtype=np.uint8)
        mock_orb_detector.detectAndCompute.return_value = ([], dummy_des)

        cv2.ORB_create.return_value = mock_orb_detector

        task.run()

        # Verify load steps
        self.mock_image_open.assert_called_with(path)
        self.mock_pil_image.convert.assert_any_call("RGBA")
        self.mock_pil_image.convert.assert_any_call("L")

        # Verify emit
        mock_emit.assert_called_once()
        args = mock_emit.call_args[0][0]
        assert args[0] == path
        assert args[1] is dummy_des

    def test_orb_task_failure(self):
        """Test OrbTask handles exceptions gracefully"""
        path = "/tmp/bad.jpg"
        task = OrbTask(path)

        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        # Raise exception during processing
        self.mock_image_open.side_effect = Exception("Load error")

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_orb_task_insufficient_features(self):
        """Test OrbTask returns None if few descriptors found"""
        path = "/tmp/test.jpg"
        task = OrbTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        mock_orb = MagicMock()
        # less than 10 descriptors
        dummy_des = np.ones((5, 32), dtype=np.uint8)
        mock_orb.detectAndCompute.return_value = ([], dummy_des)
        cv2.ORB_create.return_value = mock_orb

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_phash_task_success(self):
        """Test PhashTask computation"""
        path = "/tmp/phash.jpg"
        task = PhashTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        # Mock imagehash
        with patch("imagehash.average_hash") as mock_hash_func:
            dummy_hash = MagicMock()
            mock_hash_func.return_value = dummy_hash

            task.run()

            self.mock_image_open.assert_called_with(path)
            mock_hash_func.assert_called_once()
            mock_emit.assert_called_with((path, dummy_hash))

    def test_phash_task_failure(self):
        """Test PhashTask failure"""
        path = "/tmp/bad_phash.jpg"
        task = PhashTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        self.mock_image_open.side_effect = Exception("Fail")

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_sift_task_success(self):
        """Test SiftTask success"""
        path = "/tmp/sift.jpg"
        task = SiftTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        mock_sift = MagicMock()
        dummy_des = np.ones((20, 128), dtype=float)
        mock_sift.detectAndCompute.return_value = ([], dummy_des)
        cv2.SIFT_create.return_value = mock_sift

        task.run()

        self.mock_image_open.assert_called_with(path)
        mock_emit.assert_called_with((path, dummy_des))

    def test_sift_task_failure(self):
        """Test SiftTask failure"""
        path = "/tmp/sift_fail.jpg"
        task = SiftTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        self.mock_image_open.side_effect = Exception("Fail")

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_sift_task_insufficient_features(self):
        """Test SiftTask returns None if few descriptors"""
        path = "/tmp/sift.jpg"
        task = SiftTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        mock_sift = MagicMock()
        dummy_des = np.ones((5, 128), dtype=float)
        mock_sift.detectAndCompute.return_value = ([], dummy_des)
        cv2.SIFT_create.return_value = mock_sift

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_sn_task_success(self):
        """Test SiameseTask success"""
        path = "/tmp/sn.jpg"
        task = SiameseTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        # Mock singleton loader
        mock_loader = MagicMock()
        dummy_embedding = [0.1] * 512
        mock_loader.get_embedding.return_value = dummy_embedding
        SiameseModelLoader.return_value = mock_loader

        task.run()

        mock_loader.get_embedding.assert_called_with(path)
        mock_emit.assert_called_with((path, dummy_embedding))

    def test_sn_task_failure(self):
        """Test SiameseTask failure catch"""
        path = "/tmp/sn_fail.jpg"
        task = SiameseTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        mock_loader = MagicMock()
        mock_loader.get_embedding.side_effect = Exception("Model Error")
        SiameseModelLoader.return_value = mock_loader

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_sn_task_none_result(self):
        """Test SiameseTask handles None result from loader"""
        path = "/tmp/sn_none.jpg"
        task = SiameseTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        mock_loader = MagicMock()
        mock_loader.get_embedding.return_value = None
        SiameseModelLoader.return_value = mock_loader

        task.run()

        mock_emit.assert_called_with((path, None))

    def test_ssim_task_success(self):
        """Test SsimTask image processing"""
        path = "/tmp/ssim.jpg"
        task = SsimTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        # Override the common setup which returns a real numpy array
        # We need a Mock object to mock the .astype method call
        mock_array_obj = MagicMock()
        self.mock_np_array.return_value = mock_array_obj

        mock_float_array = MagicMock()
        mock_array_obj.astype.return_value = mock_float_array

        task.run()

        # Verify resize
        self.mock_pil_image.resize.assert_called_with(
            (256, 256), Image.Resampling.LANCZOS
        )
        # Verify emit
        mock_emit.assert_called_with((path, mock_float_array))

    def test_ssim_task_failure(self):
        """Test SsimTask failure"""
        path = "/tmp/ssim_fail.jpg"
        task = SsimTask(path)
        mock_emit = MagicMock()
        task.signals.result.connect(mock_emit)

        self.mock_image_open.side_effect = Exception("Fail")

        task.run()

        mock_emit.assert_called_with((path, None))
