"""Drive the real app: open Media Loader tab, click Download, report result."""
import os
import sys

repo_root = "/home/pkhunter/Repositories/Repos/Image-Toolkit"
sys.path.insert(0, repo_root)

from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(repo_root)

from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

os.environ.setdefault("IMAGE_TOOLKIT_TELEMETRY", "1")

_done = False


def drive():
    global _done
    if _done:
        return
    app = QApplication.instance()
    if app is None:
        QTimer.singleShot(500, drive)
        return
    wins = [w for w in app.topLevelWidgets() if w.__class__.__name__ == "MainWindow"]
    if not wins:
        QTimer.singleShot(500, drive)
        return
    win = wins[0]
    print("[repro] MainWindow found", flush=True)
    try:
        win.command_combo.setCurrentText("Web Integration")
        win._select_tab_by_name("Media Loader")
        tab = win.media_loader_tab
        from gui.src.elements.web.media_loader_tab._ui_builder import SOURCE_NHENTAI
        tab.source_combo.setCurrentIndex(SOURCE_NHENTAI)
        print("[repro] Media Loader tab found, source=", tab.source_combo.currentText(), flush=True)
        tab.nhentai_gallery_input.setText("https://nhentai.net/g/111006/")
        tab.download_dir_path.setText("/tmp/nhentai_repro_out")
        try:
            os.makedirs("/tmp/nhentai_repro_out", exist_ok=True)
        except OSError:
            pass
        print("[repro] clicking Download", flush=True)
        tab.run_button.click()
        print("[repro] clicked; worker=", tab.worker, "running=", tab.worker.isRunning() if tab.worker else None, flush=True)
        print("[repro] status=", tab.status_label.text(), flush=True)
        QTimer.singleShot(2000, report_status)
    except Exception as e:
        print("[repro] drive error: %r" % (e,), flush=True)
        _done = True


def report_status():
    global _done
    win = [w for w in QApplication.instance().topLevelWidgets() if w.__class__.__name__ == "MainWindow"][0]
    tab = win.media_loader_tab
    print("[repro] final status=", tab.status_label.text(), "run_visible=", tab.run_button.isVisible(), flush=True)
    print("[repro] worker=", tab.worker, "running=", tab.worker.isRunning() if tab.worker else None, flush=True)
    _done = True


def arm():
    QTimer.singleShot(0, drive)


from backend.src.app import launch_app  # noqa: E402

_orig_qapp_init = QApplication.__init__


def _patched_qapp_init(self, *a, **k):
    _orig_qapp_init(self, *a, **k)
    arm()


QApplication.__init__ = _patched_qapp_init

sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))
