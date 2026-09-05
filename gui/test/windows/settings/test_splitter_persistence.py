import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QSplitter

from gui.src.windows.settings.app_settings import AppSettings
from gui.src.windows.settings.splitter_persistence import (
    persist_splitter,
    restore_splitter_state,
    save_splitter_state,
)

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_save_and_restore_splitter_state():
    splitter = QSplitter(Qt.Orientation.Horizontal)
    w1 = QLabel("Panel 1")
    w2 = QLabel("Panel 2")
    splitter.addWidget(w1)
    splitter.addWidget(w2)
    splitter.resize(600, 300)
    splitter.setSizes([200, 400])

    key = "Test/test_splitter_custom"
    save_splitter_state(splitter, key)

    # Verify state was saved to AppSettings
    saved_bytes = AppSettings.splitter(key)
    assert saved_bytes is not None

    # Change sizes
    splitter.setSizes([450, 150])
    assert splitter.sizes() != [200, 400]

    # Restore state
    restored = restore_splitter_state(splitter, key)
    assert restored is True


def test_persist_splitter_auto_sync():
    splitter = QSplitter(Qt.Orientation.Horizontal)
    w1 = QLabel("A")
    w2 = QLabel("B")
    splitter.addWidget(w1)
    splitter.addWidget(w2)
    splitter.resize(500, 300)
    splitter.setSizes([150, 350])

    key = "Test/test_splitter_autosync"
    persist_splitter(splitter, key)

    # Change sizes and trigger moved signal
    splitter.setSizes([300, 200])
    splitter.splitterMoved.emit(300, 1)

    # Check that AppSettings has updated value
    saved_bytes = AppSettings.splitter(key)
    assert saved_bytes is not None


def test_restore_nonexistent_splitter():
    splitter = QSplitter(Qt.Orientation.Horizontal)
    restored = restore_splitter_state(splitter, "NonExistent/key_12345")
    assert restored is False
