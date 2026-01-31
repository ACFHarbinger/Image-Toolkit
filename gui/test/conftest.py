import sys
import pytest

from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QRunnable

# --- BLOCK HEAVY IMPORTS ---
sys.modules["backend.src.models"] = MagicMock()
sys.modules["backend.src.models.lora_diffusion"] = MagicMock()
sys.modules["backend.src.models.stable_diffusion"] = MagicMock()
sys.modules["backend.src.models.gen"] = MagicMock()
sys.modules["backend.src.models.gan"] = MagicMock()
sys.modules["backend.src.models.siamese_network"] = MagicMock()
sys.modules["backend.src.models.gan_wrapper"] = MagicMock()
sys.modules["diffusers"] = MagicMock()
sys.modules["torch.hub"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# The project root is THREE levels up from conftest.py:
# conftest.py -> test -> gui -> Image-Toolkit (Project Root)
project_root = Path(__file__).resolve().parent.parent.parent

# Add the project root to sys.path. This allows 'import gui.src...'
# to resolve 'gui' as a package within Image-Toolkit/.
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def q_app():
    """
    Ensure a QApplication exists for the entire test session.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_pixmap(q_app):
    """
    Returns a simple non-null QPixmap for testing.
    """
    pixmap = QPixmap(100, 100)
    pixmap.fill()
    return pixmap


class MockSignals(QObject):
    result = Signal(str, QPixmap)


class MockImageLoaderWorker(QRunnable):
    """
    Mock version of ImageLoaderWorker that emits signals synchronously or on demand.
    MUST inherit QRunnable for QThreadPool compatibility.
    """

    def __init__(self, path, target_size):
        super().__init__()  # Init QRunnable
        self.path = path
        self.target_size = target_size
        self.signals = MockSignals()
        self.setAutoDelete(True)

    def run(self):
        # Create a dummy pixmap
        px = QPixmap(self.target_size, self.target_size)
        px.fill()
        self.signals.result.emit(self.path, px)


@pytest.fixture
def mock_image_loader_worker(monkeypatch):
    """
    Fixture that replaces ImageLoaderWorker with the MockImageLoaderWorker.
    """
    return MockImageLoaderWorker
