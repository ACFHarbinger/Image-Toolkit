from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from gui.src.windows.login_window import LoginWindow

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
