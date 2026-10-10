"""Opt-in #729 diagnostic, hosted by the real application's guest session."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path

# Reuse the real entry point's bootstrap before importing application modules.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(str(ROOT))
from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()
from PySide6.QtCore import QObject, QTimer, QUrl  # noqa: E402


class WebEngineSpike(QObject):
    def __init__(self, output: Path, port: int):
        super().__init__()
        self.output = output
        self.port = port
        self.window = None
        self.view = None
        self.generation = 0
        self.finished = False
        self.baseline = 0
        self.started = time.monotonic()
        self.record(
            "starting",
            frozen=bool(getattr(sys, "frozen", False)),
            platform=os.environ.get("QT_QPA_PLATFORM", "default"),
        )

    def record(self, event, **fields):
        import psutil

        process = psutil.Process()
        memory = []
        for item in [process, *process.children(recursive=True)]:
            with contextlib.suppress(psutil.Error):
                memory.append({"pid": item.pid, "rss": item.memory_info().rss})
        with self.output.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "event": event,
                        "seconds": time.monotonic() - self.started,
                        "processes": memory,
                        "tree_rss": sum(p["rss"] for p in memory),
                        **fields,
                    }
                )
                + "\n"
            )
        return sum(p["rss"] for p in memory)

    def start(self, window):
        from backend.src.models.core.comfy_manager import ComfyUIManager

        self.window = window
        self.setParent(window)
        manager = ComfyUIManager.instance()
        # This diagnostic attaches to a separately supervised server; it never owns it.
        manager._port = self.port
        self.url = manager.url
        self.window.command_combo.setCurrentText("Deep Learning")
        self.window._select_tab_by_name("ComfyUI")
        self.baseline = self.record("baseline", url=self.url)
        QTimer.singleShot(60000, lambda: self.finish("timeout", 2))
        if os.environ.get("ITK_SPIKE_NO_WALLPAPER_FILTER") == "1":
            from PySide6.QtWidgets import QApplication

            QApplication.instance().removeEventFilter(window.wallpaper_tab.system_display)
            self.record("diagnostic_filter_removed")
        self.construct()

    def construct(self):
        if self.finished:
            return
        try:
            # Keep this optional: a package without WebEngine still opens the normal UI.
            from PySide6.QtWebEngineWidgets import QWebEngineView

            self.generation += 1
            self.view = QWebEngineView(self.window.comfyui_tab)
            self.view.setMinimumHeight(450)
            self.window.comfyui_tab.layout().insertWidget(0, self.view)
            self.view.page().renderProcessTerminated.connect(
                lambda status, code: self.finish(f"renderer_failed:{status}:{code}", 2)
            )
            self.view.loadFinished.connect(self.loaded)
            self.view.load(QUrl(self.url))
            self.record("constructed", generation=self.generation)
        except (ImportError, OSError) as exc:
            self.record("unavailable", error=str(exc), fallback="Guided + Open in Browser")
            self.finish("unavailable", 3)
        except Exception as exc:
            self.finish(f"construct_failed:{exc}", 2)

    def loaded(self, ok):
        if self.finished:
            return
        if not ok:
            self.finish("load_failed", 2)
            return
        QTimer.singleShot(3000, self.inspect)

    def inspect(self):
        if self.finished:
            return
        self.view.page().runJavaScript(
            "JSON.stringify({title:document.title, ready:document.readyState, "
            "body:document.body.innerText.slice(0,300), canvases:document.querySelectorAll('canvas').length})",
            self.inspected,
        )

    def inspected(self, state):
        if self.finished:
            return
        try:
            document = json.loads(state)
        except (ValueError, TypeError):
            self.finish("invalid_document_state", 2)
            return
        if (
            document.get("ready") != "complete"
            or "ComfyUI" not in document.get("title", "")
            or not document.get("canvases")
        ):
            self.finish("comfyui_not_rendered", 2)
            return
        rss = self.record("rendered", generation=self.generation, document=document)
        self.record("overhead", bytes=rss - self.baseline)
        self.view.grab().save(str(self.output.with_suffix(f".view{self.generation}.png")))
        if self.generation == 1:
            self.window._select_tab_by_name("Training")
            QTimer.singleShot(500, self.return_to_view)
        else:
            self.unload(final=True)

    def return_to_view(self):
        if self.finished:
            return
        self.window._select_tab_by_name("ComfyUI")
        self.record("cached_mount_return", generation=self.generation)
        QTimer.singleShot(1000, lambda: self.unload(final=False))

    def unload(self, final):
        if self.finished:
            return
        view, self.view = self.view, None
        view.loadFinished.disconnect(self.loaded)
        view.page().renderProcessTerminated.disconnect()
        self.window.comfyui_tab.layout().removeWidget(view)
        view.hide()
        view.destroyed.connect(lambda: self.unloaded(final))
        view.deleteLater()

    def unloaded(self, final):
        self.record("unloaded", generation=self.generation)
        if final:
            QTimer.singleShot(500, lambda: self.finish("completed", 0))
        else:
            QTimer.singleShot(500, self.construct)

    def finish(self, status, code):
        if self.finished:
            return
        self.finished = True
        self.record("finished", status=status, exit_code=code)
        from PySide6.QtWidgets import QApplication

        QApplication.instance().exit(code)


def run_spike(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8188)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    if args.output.exists():
        parser.error("output must be a new file")
    if os.environ.get("QTWEBENGINE_DISABLE_SANDBOX") or "--no-sandbox" in os.environ.get(
        "QTWEBENGINE_CHROMIUM_FLAGS", ""
    ):
        parser.error("the spike requires Chromium's sandbox")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    spike = WebEngineSpike(args.output, args.port)
    from backend.src import app as application
    from backend.src.core.vault_manager import VaultManager

    class GuestLogin(application.LoginWindow):
        def __init__(self):
            super().__init__()
            QTimer.singleShot(0, lambda: self.login_successful.emit(VaultManager.create_guest_vault("webengine-spike")))

    class SpikeWindow(application.MainWindow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            QTimer.singleShot(0, lambda: spike.start(self))

    # Instrument the real login transition and MainWindow, without shipping a
    # diagnostic auto-login or optional WebEngine import in production code.
    application.LoginWindow = GuestLogin
    application.MainWindow = SpikeWindow
    return application.launch_app({"no_dropdown": False, "enable_manager": False})


if __name__ == "__main__":
    raise SystemExit(run_spike(sys.argv[1:]))
