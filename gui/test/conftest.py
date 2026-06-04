import sys
import pytest

from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QRunnable

# --- BLOCK HEAVY IMPORTS ---
sys.modules["backend.src.models"] = MagicMock()
sys.modules["backend.src.models.basic_wrapper"] = MagicMock()
sys.modules["backend.src.models.birefnet_wrapper"] = MagicMock()
sys.modules["backend.src.models.comfy_manager"] = MagicMock()
sys.modules["backend.src.models.full_finetune"] = MagicMock()
sys.modules["backend.src.models.gan"] = MagicMock()
sys.modules["backend.src.models.gan_wrapper"] = MagicMock()
sys.modules["backend.src.models.loftr_wrapper"] = MagicMock()
sys.modules["backend.src.models.lora_diffusion"] = MagicMock()
sys.modules["backend.src.models.sd3_wrapper"] = MagicMock()
sys.modules["backend.src.models.siamese_network"] = MagicMock()
sys.modules["backend.src.models.stitch_net"] = MagicMock()
sys.modules["backend.src.models.stable_diffusion"] = MagicMock()
sys.modules["backend.src.models.gen"] = MagicMock()
sys.modules["diffusers"] = MagicMock()
sys.modules["torch.hub"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# The project root is THREE levels up from conftest.py:
# conftest.py -> test -> gui -> Image-Toolkit (Project Root)
project_root = Path(__file__).resolve().parent.parent.parent

# Add the project root to sys.path. This allows 'import gui.src...'
# to resolve 'gui' as a package within Image-Toolkit/.
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def mock_image_toolkit_paths(tmp_path, monkeypatch):
    """
    Ensure all tests run in a completely isolated sandbox and never write to the user's home directory.
    """
    from backend.src.constants import paths

    monkeypatch.setattr(paths, "IMAGE_TOOLKIT_DIR", tmp_path)
    monkeypatch.setattr(
        paths, "DAEMON_CONFIG_PATH", tmp_path / ".slideshow_config.json"
    )
    monkeypatch.setattr(paths, "THUMBNAIL_CACHE_DIR", tmp_path / "thumbnail-cache")

    try:
        from gui.src.tabs.core import listings_tab

        monkeypatch.setattr(listings_tab, "IMAGE_TOOLKIT_DIR", tmp_path)
        monkeypatch.setattr(listings_tab, "LISTINGS_FILE", tmp_path / "listings.json")
        monkeypatch.setattr(listings_tab, "ENTITIES_FILE", tmp_path / "entities.json")
        monkeypatch.setattr(
            listings_tab, "LISTING_IMAGES_DIR", tmp_path / "listing-images"
        )
    except Exception:
        pass


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
