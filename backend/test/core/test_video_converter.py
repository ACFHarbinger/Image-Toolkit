
import unittest
from unittest.mock import patch, MagicMock
from backend.src.core.video_converter import VideoFormatConverter

class TestVideoConverterReproduction(unittest.TestCase):
    @patch("subprocess.Popen")
    @patch("os.path.exists", return_value=True)
    def test_convert_video_bug_reproduction(self, mock_exists, mock_popen):
        """
        Test Case 1 (Bug Reproduction): 
        When aspect_ratio settings are passed from GUI for a preset like '16:9',
        it sends target_width=16, target_height=9.
        Currently, this results in 'scale=16:9', which is invalid for high-res video.
        
        We want to ensure that if we fix it, this specific call structure avoids 'scale=16:9'.
        But first, let's see what it generates efficiently.
        """
        process_mock = MagicMock()
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        # This simulates exactly what the GUI is sending right now for "16:9" preset
        # The GUI sends these as target_width/height because it thinks they are dimensions if "Custom" isn't fully handled or if it just passes them.
        # Actually convert_tab.py passes: ar_w=16, ar_h=9.
        # And conversion_worker.py passes them as target_width=16, target_height=9 to convert_video.
        
        VideoFormatConverter.convert_video(
            input_path="input.mp4",
            output_path="output.mp4",
            target_width=16,
            target_height=9
        )
        
        # Check arguments passed to Popen
        args, _ = mock_popen.call_args
        cmd_list = args[0]
        
        # After FIX, this should NOT have -vf scale=16:9.
        # It should actually have NO filters if aspect_ratio is not provided (ignoring the 16x9 dims).
        
        vf_part = None
        for i, arg in enumerate(cmd_list):
            if arg == "-vf":
                vf_part = cmd_list[i+1]
                break
        
        # Assertion for FIXED behavior:
        # Should be None (no filters) or at least NOT contain scale=16:9
        if vf_part:
            self.assertNotIn("scale=16:9", vf_part, "Should not scale to 16x9 pixels")
        else:
            # this is also correct behavior (ignoring bad dims)
            pass

    @patch("subprocess.Popen")
    @patch("os.path.exists", return_value=True)
    def test_convert_video_with_crop(self, mock_exists, mock_popen):
        """
        Test Case 2: Aspect Ratio Cropping
        """
        process_mock = MagicMock()
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        VideoFormatConverter.convert_video(
            input_path="input.mp4",
            output_path="output.mp4",
            target_width=16, # Should be ignored as dims
            target_height=9, # Should be ignored as dims
            aspect_ratio=1.777,
            ar_mode="crop"
        )

        args, _ = mock_popen.call_args
        cmd_list = args[0]
        
        vf_part = None
        for i, arg in enumerate(cmd_list):
            if arg == "-vf":
                vf_part = cmd_list[i+1]
                break
        
        self.assertIsNotNone(vf_part)
        self.assertIn("crop=", vf_part)
        self.assertIn("1.777", vf_part)

    @patch("subprocess.Popen")
    @patch("os.path.exists", return_value=True)
    def test_convert_video_with_stretch(self, mock_exists, mock_popen):
        """
        Test Case 3: Aspect Ratio Stretching
        """
        process_mock = MagicMock()
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        VideoFormatConverter.convert_video(
            input_path="input.mp4",
            output_path="output.mp4",
            aspect_ratio=1.777,
            ar_mode="stretch"
        )

        args, _ = mock_popen.call_args
        cmd_list = args[0]
        
        vf_part = None
        for i, arg in enumerate(cmd_list):
            if arg == "-vf":
                vf_part = cmd_list[i+1]
                break
        
        self.assertIsNotNone(vf_part)
        self.assertIn("scale=", vf_part)
        self.assertIn("setsar=1", vf_part)
        self.assertNotIn("crop=", vf_part)

    @patch("subprocess.Popen")
    @patch("os.path.exists", return_value=True)
    def test_convert_video_normal_resize(self, mock_exists, mock_popen):
        """
        Verify that legit resizing still works.
        """
        process_mock = MagicMock()
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        VideoFormatConverter.convert_video(
            input_path="input.mp4",
            output_path="output.mp4",
            target_width=1280,
            target_height=720
        )
        
        args, _ = mock_popen.call_args
        cmd_list = args[0]
        
        vf_part = None
        for i, arg in enumerate(cmd_list):
            if arg == "-vf":
                vf_part = cmd_list[i+1]
                break
        
        self.assertIn("scale=1280:720", vf_part)
