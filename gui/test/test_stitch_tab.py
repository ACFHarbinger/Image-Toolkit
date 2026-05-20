import os
from unittest.mock import patch
from gui.src.tabs.models.gen.stitch_tab import EditTab

class TestStitchTabBrowseOutput:
    def test_browse_output_starts_at_last_selected_source_directory(self, q_app):
        # Create EditTab instance
        tab = EditTab()
        
        # Setup mock frame paths mimicking added source frames
        tab._frame_paths = ["/home/user/pictures/frame1.png", "/home/user/downloads/frame2.png"]
        
        # Mock QFileDialog.getSaveFileName to avoid popping up UI
        with patch("gui.src.tabs.models.gen.stitch_tab.QFileDialog.getSaveFileName") as mock_save_dialog:
            mock_save_dialog.return_value = ("/home/user/downloads/my_panorama.png", "Images (*.png *.webp *.jpg)")
            
            tab._browse_output()
            
            # Assert that getSaveFileName was called
            mock_save_dialog.assert_called_once()
            
            # Check the third positional argument (default_file) passed to QFileDialog.getSaveFileName
            # It should start in the directory of the last frame path: "/home/user/downloads"
            args, kwargs = mock_save_dialog.call_args
            assert args[2] == os.path.normpath("/home/user/downloads/panorama.png")
            
            # Verify the output path was set to the mock returned path
            assert tab._output_path.text() == "/home/user/downloads/my_panorama.png"

    def test_browse_output_preserves_existing_filename(self, q_app):
        tab = EditTab()
        tab._frame_paths = ["/home/user/pictures/frame1.png", "/home/user/downloads/frame2.png"]
        tab._output_path.setText("my_custom_panorama.png")
        
        with patch("gui.src.tabs.models.gen.stitch_tab.QFileDialog.getSaveFileName") as mock_save_dialog:
            mock_save_dialog.return_value = ("", "")
            
            tab._browse_output()
            
            args, kwargs = mock_save_dialog.call_args
            assert args[2] == os.path.normpath("/home/user/downloads/my_custom_panorama.png")
