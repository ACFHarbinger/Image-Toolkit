import contextlib
import importlib.machinery
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

# --- BLOCK HEAVY IMPORTS ---
sys.modules["backend.src.models"] = MagicMock()
sys.modules["backend.src.models.core"] = MagicMock()
sys.modules["backend.src.models.tuning"] = MagicMock()
sys.modules["backend.src.models.tuning.lo_ra_tuner"] = MagicMock()
sys.modules["backend.src.models.wrappers"] = MagicMock()
sys.modules["backend.src.models.wrappers.basic_wrapper"] = MagicMock()
sys.modules["backend.src.models.wrappers.birefnet_wrapper"] = MagicMock()
sys.modules["backend.src.models.core.comfy_manager"] = MagicMock()
sys.modules["backend.src.models.full_finetune"] = MagicMock()
sys.modules["backend.src.models.core.gan"] = MagicMock()
sys.modules["backend.src.models.wrappers.gan_wrapper"] = MagicMock()
sys.modules["backend.src.models.wrappers.loftr_wrapper"] = MagicMock()
sys.modules["backend.src.models.lora_diffusion"] = MagicMock()
sys.modules["backend.src.models.wrappers.sd3_wrapper"] = MagicMock()
sys.modules["backend.src.models.core.siamese_network"] = MagicMock()
sys.modules["backend.src.models.core.stitch_net"] = MagicMock()
sys.modules["backend.src.models.stable_diffusion"] = MagicMock()
sys.modules["backend.src.models.gen"] = MagicMock()

diffusers_mock = MagicMock()
diffusers_mock.__spec__ = importlib.machinery.ModuleSpec("diffusers", None)
sys.modules["diffusers"] = diffusers_mock
sys.modules["torch.hub"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# The project root is THREE levels up from conftest.py:
# conftest.py -> test -> gui -> Image-Toolkit (Project Root)
project_root = Path(__file__).resolve().parent.parent.parent

# Add the project root to sys.path. This allows 'import gui.src...'
# to resolve 'gui' as a package within Image-Toolkit/.
sys.path.insert(0, str(project_root))

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

apply_patch()


@pytest.fixture(autouse=True)
def mock_image_toolkit_paths(tmp_path, monkeypatch):
    """
    Ensure all tests run in a completely isolated sandbox and never write to the user's home directory.
    """
    import backend.src.constants as constants
    from backend.src.constants import paths

    fake_config_path = tmp_path / ".slideshow_config.json"

    monkeypatch.setattr(paths, "IMAGE_TOOLKIT_DIR", tmp_path)
    monkeypatch.setattr(
        paths, "DAEMON_CONFIG_PATH", fake_config_path
    )
    monkeypatch.setattr(paths, "THUMBNAIL_CACHE_DIR", tmp_path / "thumbnail-cache")

    monkeypatch.setattr(constants, "IMAGE_TOOLKIT_DIR", tmp_path)
    monkeypatch.setattr(constants, "DAEMON_CONFIG_PATH", fake_config_path)

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

    try:
        import gui.src.tabs.core.elements.system_display_subtab as subtab
        monkeypatch.setattr(subtab, "DAEMON_CONFIG_PATH", fake_config_path)
        monkeypatch.setattr(subtab, "ROOT_DIR", tmp_path)
    except Exception:
        pass

    try:
        import gui.src.tabs.core.elements.common.wallpaper_common_base as common_base
        monkeypatch.setattr(common_base, "DAEMON_CONFIG_PATH", fake_config_path)
    except Exception:
        pass

    try:
        import gui.src.windows.settings.settings_window as settings_window
        monkeypatch.setattr(settings_window, "DAEMON_CONFIG_PATH", fake_config_path)
        monkeypatch.setattr(settings_window, "IMAGE_TOOLKIT_DIR", tmp_path)
    except Exception:
        pass


@pytest.fixture(autouse=True, scope="function")
def cleanup_active_workers_and_timers(q_app):
    from PySide6.QtCore import QThreadPool, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    started_workers = []
    original_start = QThreadPool.globalInstance().start

    def mock_start(runnable, priority=0):
        started_workers.append(runnable)
        return original_start(runnable, priority)

    QThreadPool.globalInstance().start = mock_start

    yield

    QThreadPool.globalInstance().start = original_start

    for worker in started_workers:
        try:
            if hasattr(worker, "stop"):
                worker.stop()
        except Exception:
            pass

    for widget in QApplication.topLevelWidgets():
        for timer in widget.findChildren(QTimer):
            with contextlib.suppress(Exception):
                timer.stop()
        for subtab in widget.findChildren(QWidget):
            try:
                if hasattr(subtab, "slideshow_timer") and subtab.slideshow_timer:
                    subtab.slideshow_timer.stop()
            except Exception:
                pass
            try:
                if hasattr(subtab, "countdown_timer") and subtab.countdown_timer:
                    subtab.countdown_timer.stop()
            except Exception:
                pass

    # Close and delete all top-level widgets to prevent leaks and styling hangs
    for widget in QApplication.topLevelWidgets():
        try:
            widget.close()
            widget.deleteLater()
        except Exception:
            pass

    for _ in range(5):
        QApplication.processEvents()
    QThreadPool.globalInstance().waitForDone(500)


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


def pytest_addoption(parser):
    parser.addoption(
        "--run-gui",
        action="store_true",
        default=False,
        help="Run tests that launch/create GUI windows or tabs",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "gui: Mark test as requiring/launching a GUI window or tab"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-gui"):
        # --run-gui option passed: do not skip
        return

    skip_gui = pytest.mark.skip(reason="Needs --run-gui option to run")
    for item in items:
        if item.get_closest_marker("gui") is not None:
            item.add_marker(skip_gui)
