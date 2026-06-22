import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from gui.src.windows.login_window import LoginWindow

pytestmark = pytest.mark.gui

class TestLoginWindowKeyPress:
    def test_escape_key_closes_window(self, q_app):
        # Create instance of LoginWindow
        window = LoginWindow()
        
        # Mock the close method to verify it's called
        window.close = MagicMock()
        
        # Create a QKeyEvent for escape
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        
        # Call the keyPressEvent directly
        window.keyPressEvent(event)
        
        # Assert that close was called
        window.close.assert_called_once()
        
    def test_other_key_does_not_close_window(self, q_app):
        window = LoginWindow()
        window.close = MagicMock()
        
        # Send key 'A' instead of Escape
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        
        window.keyPressEvent(event)
        
        window.close.assert_not_called()


class TestLoginWindowCryptoAutoLoad:
    def test_copy_template_crypto_files(self, q_app, tmp_path):
        from unittest.mock import patch
        
        template_dir = tmp_path / "assets" / "cryptography"
        template_dir.mkdir(parents=True, exist_ok=True)
        
        target_dir = tmp_path / "image-toolkit" / "cryptography"
        
        # Create template files
        file1 = template_dir / "my_keystore.p12"
        file1.write_text("keystore data")
        file2 = template_dir / "pepper.txt"
        file2.write_text("pepper data")
        
        # Also create a file in target_dir beforehand to check it doesn't get overwritten
        target_dir.mkdir(parents=True, exist_ok=True)
        existing_file = target_dir / "pepper.txt"
        existing_file.write_text("original pepper data")
        
        window = LoginWindow()
        
        with (
            patch("gui.src.windows.login_window.udef.TEMPLATE_CRYPTO_DIR", template_dir),
            patch("gui.src.windows.login_window.udef.CRYPTO_DIR", target_dir)
        ):
            window._copy_template_crypto_files()
            
            # Check file1 (which didn't exist) was copied
            assert (target_dir / "my_keystore.p12").exists()
            assert (target_dir / "my_keystore.p12").read_text() == "keystore data"
            
            # Check file2 (which already existed) was not overwritten
            assert (target_dir / "pepper.txt").exists()
            assert (target_dir / "pepper.txt").read_text() == "original pepper data"

