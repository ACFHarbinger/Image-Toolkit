import contextlib
import importlib.machinery
import os
import sys
import tempfile

# --- ISOLATE THE CONFIG ROOT (must precede any PySide6 import) ---
# Qt resolves and caches its settings root (QSettings, and its own
# QtProject.conf that persists QFileDialog sidebar bookmarks) on first use.
# Point the whole config root at a throwaway dir so no test can write to the
# user's real ~/.config — neither our QSettings("ImageToolkit", ...) nor Qt's
# internal file-dialog "shortcuts" list. Session-wide; the dir dies with the
# process, so every change a test makes here is transient.
if "PYTEST_IT_CONFIG_HOME" not in os.environ:
    os.environ["PYTEST_IT_CONFIG_HOME"] = tempfile.mkdtemp(prefix="it-test-config-")
os.environ["XDG_CONFIG_HOME"] = os.environ["PYTEST_IT_CONFIG_HOME"]

# --- BLOCK HEAVY IMPORTS ---
# Build the mocked backend.src.models tree as REAL package modules (with
# __path__) whose leaf submodules are MagicMock. A flat
# sys.modules["backend.src.models.wrappers"] = MagicMock() made any later
# "from backend.src.models.wrappers.X import Y" in the SAME pytest process
# fail with "'...wrappers' is not a package" — which broke backend/test/
# models collection when gui/test/models and backend/test/models were
# collected together (#375). Real packages + mocked leaves let both sides
# import: gui gets the mock (heavy torch/diffusers never load), backend
# tests that import BEFORE the gui session still resolve... (see restore
# block below for the combined-session case).
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication


def _mock_submodule(fullname: str) -> "MagicMock":
    mod = MagicMock()
    mod.__name__ = fullname
    return mod


def _mock_package(fullname: str) -> "types.ModuleType":
    """Create a real package module (__path__ set) so submodule imports
    resolve through it instead of failing with 'is not a package'."""
    pkg = types.ModuleType(fullname)
    pkg.__path__ = []
    pkg.__spec__ = importlib.machinery.ModuleSpec(fullname, None)
    sys.modules.setdefault(fullname, pkg)
    return pkg


def _mock_model_tree():
    """Mock backend.src.models.* (and asp_backend.models.stitch_net) as a
    real-package tree so gui tests import quickly AND backend tests can
    still collect in the same process."""
    models_pkg = _mock_package("backend.src.models")
    core_pkg = _mock_package("backend.src.models.core")
    tuning_pkg = _mock_package("backend.src.models.tuning")
    wrappers_pkg = _mock_package("backend.src.models.wrappers")
    gen_pkg = _mock_package("backend.src.models.gen")
    # Attach packages to their parents for attribute-style access.
    models_pkg.core = core_pkg
    models_pkg.tuning = tuning_pkg
    models_pkg.wrappers = wrappers_pkg
    models_pkg.gen = gen_pkg
    # Leaf modules (each a MagicMock) — the names gui code imports.
    leaves = [
        "backend.src.models.core.comfy_manager",
        "backend.src.models.core.gan",
        "backend.src.models.core.siamese_network",
        "backend.src.models.full_finetune",
        "backend.src.models.lora_diffusion",
        "backend.src.models.stable_diffusion",
        "backend.src.models.tuning.lo_ra_tuner",
        "backend.src.models.wrappers.basic_wrapper",
        "backend.src.models.wrappers.birefnet_wrapper",
        "backend.src.models.wrappers.gan_wrapper",
        "backend.src.models.wrappers.loftr_wrapper",
        "backend.src.models.wrappers.sd3_wrapper",
        "asp_backend.models.stitch_net",
    ]
    for leaf in leaves:
        sys.modules[leaf] = _mock_submodule(leaf)
    # Sentinel: lets backend/test/conftest.py detect and restore the real
    # packages when both suites share one pytest process (#375).
    sys.modules.setdefault("_devtool_mocked_backend_models", True)
    return models_pkg


_mock_model_tree()

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
# ASP and Manga Colorization & Animation live in their own submodules;
# see git/scripts/_submodule_bootstrap.py for why this isn't a plain
# sys.path.insert.
from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(str(project_root))

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

apply_patch()


def _close_without_modal(widget) -> None:
    """close() a top-level widget without its closeEvent blocking on a modal.

    SettingsWindow.closeEvent pops an "unsaved settings?" QMessageBox and
    spins dialog.exec() forever when no one clicks it (CI hang, 2026-09-01).
    """
    if hasattr(widget, "_has_unsaved_settings"):
        widget._has_unsaved_settings = lambda: False
    widget.close()


@pytest.fixture(autouse=True)
def isolate_persistent_settings(tmp_path, monkeypatch):
    """Per-test isolation for everything the app persists outside its data dir.

    ``XDG_CONFIG_HOME`` (set at conftest import) already keeps writes out of the
    real ``~/.config``; this narrows it to per-test so state can't bleed between
    tests:

    - ``AppSettings`` — every ``QSettings("ImageToolkit", ...)`` access goes
      through ``AppSettings._q()`` (verified: no direct ``QSettings(`` calls
      elsewhere in ``gui/src``), so pointing that at a fresh per-test ini file
      isolates favourites, session state, geometry, splitters, prefs, etc.
    - ``_KEYBINDINGS_PATH`` — ``~/.image-toolkit/keybindings.json`` is derived
      from ``Path.home()`` at import, not from the patched ``IMAGE_TOOLKIT_DIR``,
      so it needs its own redirect (both module bindings).
    """
    from PySide6.QtCore import QSettings

    ini = tmp_path / "app_settings.ini"

    try:
        from gui.src.windows.settings.app_settings import AppSettings

        monkeypatch.setattr(
            AppSettings,
            "_q",
            classmethod(lambda cls: QSettings(str(ini), QSettings.Format.IniFormat)),
        )
    except Exception:
        pass

    kb = tmp_path / "keybindings.json"
    for modname in (
        "gui.src.constants.utils",
        "gui.src.utils.manager.shortcut_manager",
    ):
        try:
            mod = importlib.import_module(modname)
            if hasattr(mod, "_KEYBINDINGS_PATH"):
                monkeypatch.setattr(mod, "_KEYBINDINGS_PATH", kb)
        except Exception:
            pass


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
        from gui.src.tabs.database import listings_tab

        monkeypatch.setattr(listings_tab, "IMAGE_TOOLKIT_DIR", tmp_path)
        monkeypatch.setattr(listings_tab, "LISTINGS_FILE", tmp_path / "listings.json")
        monkeypatch.setattr(listings_tab, "ENTITIES_FILE", tmp_path / "entities.json")
        monkeypatch.setattr(
            listings_tab, "LISTING_IMAGES_DIR", tmp_path / "listing-images"
        )
    except Exception:
        pass

    try:
        import gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon as subtab_daemon
        import gui.src.tabs.core.wallpaper_tab.system_display_subtab._slideshow as subtab_slideshow
        monkeypatch.setattr(subtab_daemon, "DAEMON_CONFIG_PATH", fake_config_path)
        monkeypatch.setattr(subtab_daemon, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(subtab_slideshow, "DAEMON_CONFIG_PATH", fake_config_path)
    except Exception:
        pass

    try:
        import gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._widget_ui_lifecycle as common_base_ui_lifecycle
        monkeypatch.setattr(common_base_ui_lifecycle, "DAEMON_CONFIG_PATH", fake_config_path)
    except Exception:
        pass

    try:
        import gui.src.windows.settings._reset_state as settings_window_reset_state
        monkeypatch.setattr(settings_window_reset_state, "DAEMON_CONFIG_PATH", fake_config_path)
        monkeypatch.setattr(settings_window_reset_state, "IMAGE_TOOLKIT_DIR", tmp_path)
    except Exception:
        pass

    # Belt-and-braces: any module that did `from ...constants import
    # IMAGE_TOOLKIT_DIR` holds its own name binding that patching `paths` /
    # `constants` above does not reach. Sweep every already-imported module and
    # repoint a stale binding at tmp_path so no test can write to the real
    # ~/.image-toolkit (e.g. the extractor's .extraction_history.json).
    _tmp_s = str(tmp_path)
    for _name, _mod in list(sys.modules.items()):
        # torch._classes and other lazy proxies raise on arbitrary getattr.
        if _mod is None or _name.startswith(("torch.", "torch._")):
            continue
        try:
            _val = _mod.__dict__.get("IMAGE_TOOLKIT_DIR")
        except Exception:
            continue
        if _val is not None and str(_val) != _tmp_s:
            with contextlib.suppress(Exception):
                monkeypatch.setattr(_mod, "IMAGE_TOOLKIT_DIR", tmp_path, raising=False)


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

    # Snapshot the windows that already exist so teardown only walks the ones
    # this test created. Walking EVERY accumulated top-level window each test is
    # quadratic: deleteLater()'d windows are never actually destroyed
    # (processEvents() does not deliver DeferredDelete), so topLevelWidgets()
    # grows unbounded and this findChildren/hasattr sweep climbs into the
    # millions of calls on late tests — the gui/test/windows/ 100%-CPU hang
    # (deepseek investigation 2026-08-23). Walking just the new windows is
    # sufficient: every older window's timers were already stopped by its own
    # teardown. We deliberately keep the widgets alive (no forced DeferredDelete
    # delivery): destroying them under test fixtures that later call close() on
    # the same wrappers segfaults in C++ virtual dispatch.
    preexisting = {id(w) for w in QApplication.topLevelWidgets()}

    yield

    QThreadPool.globalInstance().start = original_start

    for worker in started_workers:
        try:
            if hasattr(worker, "stop"):
                worker.stop()
        except Exception:
            pass

    for widget in QApplication.topLevelWidgets():
        if id(widget) in preexisting:
            continue
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
            _close_without_modal(widget)
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
