"""QWebChannel bridge for embedded ComfyUI (#755).

Injects ``comfy_bridge.js`` and Qt's ``qwebchannel.js`` into the embedded
QWebEngineView (MainWorld, DocumentReady) to provide:
  1. Active-node highlighting and auto-panning in LiteGraph.
  2. Bidirectional parameter sync between Guided mode widgets and graph nodes.
  3. Image path handoff to LoadImage nodes.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QObject, Signal, Slot

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineScript
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    QWebChannel = None
    QWebEngineScript = None
    QWebEngineView = None
    WEB_ENGINE_AVAILABLE = False

_SCRIPT_PATH = Path(__file__).resolve().parent / "comfy_bridge.js"
_CACHED_COMBINED_SCRIPT: str | None = None


def get_qwebchannel_js() -> str:
    """Return the official Qt qwebchannel.js client library from Qt resources."""
    # Ensure QWebChannel resource registry is active
    _wc = QWebChannel()
    resource_file = QFile(":/qtwebchannel/qwebchannel.js")
    if resource_file.open(QIODevice.OpenModeFlag.ReadOnly):
        content = bytes(resource_file.readAll()).decode("utf-8")
        resource_file.close()
        return content
    return ""


def get_comfy_bridge_js() -> str:
    """Read comfy_bridge.js from disk."""
    if _SCRIPT_PATH.is_file():
        return _SCRIPT_PATH.read_text(encoding="utf-8")
    return ""


def get_combined_injection_script() -> str:
    """Combine qwebchannel.js and comfy_bridge.js into a single injection script."""
    global _CACHED_COMBINED_SCRIPT
    if _CACHED_COMBINED_SCRIPT is None:
        qwebchannel_code = get_qwebchannel_js()
        bridge_code = get_comfy_bridge_js()
        _CACHED_COMBINED_SCRIPT = f"{qwebchannel_code}\n\n{bridge_code}"
    return _CACHED_COMBINED_SCRIPT


class ComfyBridge(QObject):
    """Bidirectional QWebChannel bridge object registered as 'comfyBridge'."""

    # Python -> JS signals
    highlight_node_requested = Signal(str)
    sync_param_requested = Signal(str, str, str)  # (node_id, widget_name, value_json)
    set_image_requested = Signal(str, str)        # (node_id, image_filename)

    # JS -> Python notifications
    bridge_ready = Signal()
    node_highlighted = Signal(str)
    node_highlight_failed = Signal(str, str)
    param_changed_in_graph = Signal(str, str, str)  # (node_id, widget_name, raw_value)
    log_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    # --- Slots called by JavaScript over QWebChannel ---

    @Slot()
    def notifyBridgeReady(self) -> None:
        self._is_ready = True
        self.bridge_ready.emit()

    @Slot(str)
    def notifyNodeHighlighted(self, node_id: str) -> None:
        self.node_highlighted.emit(node_id)

    @Slot(str, str)
    def notifyNodeHighlightFailed(self, node_id: str, reason: str) -> None:
        self.node_highlight_failed.emit(node_id, reason)

    @Slot(str, str, str)
    def notifyParamChanged(self, node_id: str, widget_name: str, value: str) -> None:
        self.param_changed_in_graph.emit(node_id, widget_name, value)

    @Slot(str)
    def log(self, message: str) -> None:
        self.log_message.emit(message)

    # --- Public Python API ---

    def highlight_node(self, node_id: str | int) -> None:
        """Request the embedded canvas to pan, zoom and pulse node_id."""
        self.highlight_node_requested.emit(str(node_id))

    def sync_param(self, node_id: str | int, widget_name: str, value: object) -> None:
        """Update widget_name on node_id in the graph canvas."""
        val_str = json.dumps(value) if not isinstance(value, str) else value
        self.sync_param_requested.emit(str(node_id), str(widget_name), val_str)

    def set_image_node(self, node_id: str | int, image_filename: str) -> None:
        """Set the image parameter on a LoadImage node."""
        self.set_image_requested.emit(str(node_id), str(image_filename))


def setup_comfy_web_channel(
    view: QWebEngineView, bridge: ComfyBridge | None = None
) -> tuple[QWebChannel, ComfyBridge]:
    """Register QWebChannel and inject comfy_bridge.js into the view's page.

    The script is injected into MainWorld so it can access window.app / LiteGraph,
    and runs on DocumentReady.
    """
    if not WEB_ENGINE_AVAILABLE:
        raise RuntimeError("QtWebEngine or QtWebChannel is not available.")

    bridge = bridge or ComfyBridge(view)
    channel = QWebChannel(view)
    channel.registerObject("comfyBridge", bridge)

    page = view.page()
    page.setWebChannel(channel)

    script = QWebEngineScript()
    script.setName("comfy_bridge")
    script.setSourceCode(get_combined_injection_script())
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setRunsOnSubFrames(False)
    page.scripts().insert(script)

    return channel, bridge
