"""Unit tests for ComfyBridge, comfy_bridge.js injection, and parameter sync (#755)."""
import http.server
import json
import threading
from unittest.mock import MagicMock

import pytest
import shiboken6
from backend.src.constants.comfy import ServerState
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
from gui.src.tabs.models.gen.comfy_bridge import (
    ComfyBridge,
    get_combined_injection_script,
    get_comfy_bridge_js,
    get_qwebchannel_js,
    setup_comfy_web_channel,
)
from gui.src.tabs.models.gen.comfy_generate_tab import ComfyUITab
from gui.src.tabs.models.guidance_diff_widget import GuidanceDiffWidget

pytestmark = pytest.mark.gui


class TestComfyBridgeScripts:
    def test_get_qwebchannel_js_returns_content(self):
        js = get_qwebchannel_js()
        assert isinstance(js, str)
        assert len(js) > 100
        assert "QWebChannel" in js

    def test_get_comfy_bridge_js_returns_content(self):
        js = get_comfy_bridge_js()
        assert isinstance(js, str)
        assert len(js) > 100
        assert "highlightNode" in js
        assert "setNodeWidgetValue" in js

    def test_get_combined_injection_script(self):
        combined = get_combined_injection_script()
        assert "QWebChannel" in combined
        assert "comfy_bridge" in combined
        assert "window.comfyBridgeHelper" in combined


class TestComfyBridgeQObject:
    def test_initial_state(self, q_app):
        bridge = ComfyBridge()
        assert not bridge.is_ready

    def test_notify_bridge_ready(self, q_app):
        bridge = ComfyBridge()
        ready_emitted = []
        bridge.bridge_ready.connect(lambda: ready_emitted.append(True))
        bridge.notifyBridgeReady()
        assert bridge.is_ready
        assert ready_emitted == [True]

    def test_highlight_node_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.highlight_node_requested.connect(requested.append)
        bridge.highlight_node(3)
        assert requested == ["3"]
        bridge.highlight_node("node_7")
        assert requested == ["3", "node_7"]

    def test_sync_param_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.sync_param_requested.connect(lambda nid, param, val: requested.append((nid, param, val)))
        bridge.sync_param(1, "ckpt_name", "v1-5-pruned.safetensors")
        assert requested == [("1", "ckpt_name", '"v1-5-pruned.safetensors"')]

        # Test object/numeric serialization
        bridge.sync_param(3, "cfg", 7.5)
        assert requested[-1] == ("3", "cfg", "7.5")

    def test_bind_template_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.bind_template_requested.connect(requested.append)
        bridge.bind_template({"1": {"class_type": "CheckpointLoaderSimple"}})
        assert len(requested) == 1
        assert "CheckpointLoaderSimple" in requested[0]

    def test_load_template_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.load_template_requested.connect(requested.append)
        bridge.load_template({"1": {"class_type": "CheckpointLoaderSimple"}})
        assert len(requested) == 1
        assert "CheckpointLoaderSimple" in requested[0]

    def test_notify_template_loaded_emits_signal(self, q_app):
        bridge = ComfyBridge()
        loaded = []
        bridge.template_loaded.connect(loaded.append)
        bridge.notifyTemplateLoaded(True)
        assert loaded == [True]
        bridge.notifyTemplateLoaded(False)
        assert loaded == [True, False]

    def test_set_image_node_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.set_image_requested.connect(lambda nid, img: requested.append((nid, img)))
        bridge.set_image_node(9, "pose.png")
        assert requested == [("9", '"pose.png"')]

    def test_js_to_python_notifications(self, q_app):
        bridge = ComfyBridge()
        highlighted = []
        failed = []
        params = []
        logs = []

        bridge.node_highlighted.connect(highlighted.append)
        bridge.node_highlight_failed.connect(lambda nid, err: failed.append((nid, err)))
        bridge.param_changed_in_graph.connect(lambda nid, name, val: params.append((nid, name, val)))
        bridge.log_message.connect(logs.append)

        bridge.notifyNodeHighlighted("3")
        assert highlighted == ["3"]

        bridge.notifyNodeHighlightFailed("99", "Not found")
        assert failed == [("99", "Not found")]

        bridge.notifyParamChanged("2", "text", "new prompt")
        assert params == [("2", "text", "new prompt")]

        bridge.log("canvas ready")
        assert logs == ["canvas ready"]


class TestSetupComfyWebChannel:
    def test_setup_registers_object_and_injects_script(self, q_app):
        view = QWebEngineView()
        try:
            channel, bridge = setup_comfy_web_channel(view, allowed_url="http://127.0.0.1:8188")
            assert bridge is not None
            assert channel is not None
            assert "comfyBridge" in channel.registeredObjects()
            scripts = view.page().scripts().toList()
            assert any(s.name() == "comfy_bridge" for s in scripts)
        finally:
            view.page().setWebChannel(None)
            shiboken6.delete(view)
            q_app.processEvents()


class TestComfyUITabBridge:
    @pytest.fixture
    def tab(self, q_app):
        manager = MagicMock(state=ServerState.STOPPED, owns_server=False, port=8188, url="http://127.0.0.1:8188")
        controller = ComfyWorkspaceController(manager=manager)
        widget = ComfyUITab(controller=controller)
        yield widget
        widget.close()
        controller.shutdown()
        q_app.processEvents()

    def test_highlight_node_without_bridge_fails_open(self, tab):
        # When bridge is not mounted, returns False without crashing
        assert not tab.highlight_node("3")

    def test_highlight_node_with_bridge_delegates(self, tab):
        mock_bridge = MagicMock()
        tab._bridge = mock_bridge
        assert tab.highlight_node("3")
        mock_bridge.highlight_node.assert_called_once_with("3")

    def test_param_changed_from_graph_updates_ui(self, tab):
        # Default mode is controlnet_pose:
        # checkpoint_node: 1 (ckpt_name), positive_node: 2 (text), negative_node: 3 (text),
        # extra_node: 8 (control_net_name), image_node: 9 (image)
        tab._on_param_changed_from_graph("1", "ckpt_name", "new_model.safetensors")
        assert tab._base_ckpt_edit.text() == "new_model.safetensors"

        tab._on_param_changed_from_graph("2", "text", "1girl in rain")
        assert tab._prompt_edit.text() == "1girl in rain"

        tab._on_param_changed_from_graph("3", "text", "worst quality, artifacts")
        assert tab._negative_prompt_edit.text() == "worst quality, artifacts"

        tab._on_param_changed_from_graph("8", "control_net_name", "control_canny.pth")
        assert tab._extra_ckpt_edit.text() == "control_canny.pth"

        # Mapped server token maps back to local path
        tab._token_to_local["uploaded_pose.png"] = "/path/to/pose.png"
        tab._on_param_changed_from_graph("9", "image", "uploaded_pose.png")
        assert tab._image_edit.text() == "/path/to/pose.png"

        # Unmapped server token displays the token string directly
        tab._on_param_changed_from_graph("9", "image", "raw_server_token.png")
        assert tab._image_edit.text() == "raw_server_token.png"

    def test_guided_ui_changes_sync_to_bridge(self, tab):
        mock_bridge = MagicMock()
        tab._bridge = mock_bridge

        tab._base_ckpt_edit.setText("animagine_v3.safetensors")
        mock_bridge.sync_param.assert_any_call("1", "ckpt_name", "animagine_v3.safetensors")

        tab._prompt_edit.setText("scenery, mountain")
        mock_bridge.sync_param.assert_any_call("2", "text", "scenery, mountain")

        tab._negative_prompt_edit.setText("monochrome")
        mock_bridge.sync_param.assert_any_call("3", "text", "monochrome")

        tab._extra_ckpt_edit.setText("extra_weights.pth")
        mock_bridge.sync_param.assert_any_call("8", "control_net_name", "extra_weights.pth")

        tab._server_tokens.add("existing_token.png")
        tab._image_edit.setText("existing_token.png")
        mock_bridge.set_image_node.assert_called_with("9", "existing_token.png")

    def test_async_image_upload_and_token_mapping(self, tab, tmp_path, q_app):
        mock_bridge = MagicMock()
        tab._bridge = mock_bridge
        tab._manager.is_running = True
        tab._manager.upload_image.return_value = "server_uploaded_pose.png"

        img_file = tmp_path / "local_pose.png"
        img_file.write_bytes(b"mock_png_bytes")

        # Trigger async image upload via textChanged
        tab._image_edit.setText(str(img_file))

        # Spin event loop briefly for QThread worker to complete
        loop = QEventLoop()
        QTimer.singleShot(200, loop.quit)
        loop.exec()

        tab._manager.upload_image.assert_called_once_with(str(img_file))
        assert tab._local_to_token[str(img_file)] == "server_uploaded_pose.png"
        assert tab._token_to_local["server_uploaded_pose.png"] == str(img_file)
        mock_bridge.set_image_node.assert_called_with("9", "server_uploaded_pose.png")

        # Reverse sync: graph reports server token -> UI shows local path
        tab._on_param_changed_from_graph("9", "image", "server_uploaded_pose.png")
        assert tab._image_edit.text() == str(img_file)

        # Queue worker reuses cached token without redundant upload
        tab._manager.upload_image.reset_mock()
        tab._manager.queue_workflow.return_value = "prompt-123"
        tab._queue_workflow_worker(
            "controlnet_pose", str(img_file), "base.safetensors", "cn.pth", "pos", "neg",
        )
        tab._manager.upload_image.assert_not_called()
        submitted = tab._manager.queue_workflow.call_args[0][0]
        assert submitted["9"]["inputs"]["image"] == "server_uploaded_pose.png"

    def test_stale_upload_does_not_replace_new_selection(self, tab):
        tab._bridge = MagicMock()
        tab._image_edit.setText("new.png")
        request = tab._image_request
        tab._on_image_uploaded((request - 1, "9", "old.png", "old-token.png"))
        tab._bridge.set_image_node.assert_not_called()
        assert "old.png" not in tab._local_to_token

    def test_closed_tab_ignores_upload_completion(self, tab):
        tab._image_edit.setText("old.png")
        request = tab._image_request
        tab.close()
        tab._on_image_uploaded((request, "9", "old.png", "old-token.png"))
        assert not tab._local_to_token

    def test_graph_token_is_reused_when_queuing(self, tab):
        from unittest.mock import patch
        tab._on_param_changed_from_graph("9", "image", "remote-only.png")
        with patch("gui.src.tabs.models.gen.comfy_generate_tab._queue_workflow") as queue:
            tab._queue_workflow_worker("controlnet_pose", "remote-only.png", "base", "extra", "p", "n")
        assert queue.call_args.kwargs["uploaded_image"] == "remote-only.png"

    def test_mode_switch_syncs_all_parameters(self, tab):
        mock_bridge = MagicMock()
        tab._bridge = mock_bridge

        idx = tab._mode_combo.findData("ipadapter_reference")
        tab._mode_combo.setCurrentIndex(idx)

        mock_bridge.bind_template.assert_called_once()
        assert mock_bridge.bind_template.call_args.args[0]["3"]["class_type"]
        mock_bridge.sync_param.assert_not_called()


class TestGuidanceFocusButton:
    def test_guidance_diff_row_has_focus_button(self, q_app):
        from backend.src.core.guidance_schema import (
            GuidanceResponse,
            GuidanceValidation,
            ParamChange,
            SuggestionVerdict,
            Verdict,
        )

        param_change = ParamChange(
            node_id="3",
            input_name="cfg",
            from_value=8.5,
            to_value=6.0,
            reason="Lower CFG to prevent ringing",
        )
        response = GuidanceResponse(
            schema_version=1,
            workflow_hash="test_hash",
            workflow_param_changes=(param_change,),
            diagnosis="High CFG guidance burn",
        )
        validation = GuidanceValidation(
            response=response,
            verdicts=(
                SuggestionVerdict(
                    change=param_change,
                    status=Verdict.VALID,
                    detail="Valid CFG patch",
                ),
            ),
        )

        widget = GuidanceDiffWidget()
        requested_nodes = []
        widget.node_highlight_requested.connect(requested_nodes.append)

        widget.set_guidance(workflow={"3": {"inputs": {"cfg": 8.5}}}, validation=validation)

        from PySide6.QtWidgets import QPushButton
        focus_buttons = widget.findChildren(QPushButton, "guidance_focus_3_cfg")
        assert len(focus_buttons) == 1
        focus_btn = focus_buttons[0]
        assert focus_btn.text() == "Focus"

        focus_btn.click()
        assert requested_nodes == ["3"]

    def test_workspace_host_highlight_node(self, q_app):
        from gui.src.preferences import (
            MemoryPreferenceAdapter,
            PreferenceScope,
            PreferenceStore,
        )
        from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

        store = PreferenceStore(lazy_adapters=True)
        store.register_adapter(PreferenceScope.DEVICE, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())
        store.register_adapter(PreferenceScope.SESSION, MemoryPreferenceAdapter())
        host = DeepLearningWorkspaceHost(preference_store=store)

        mock_comfy = MagicMock()
        mock_comfy.highlight_node.return_value = True
        host._ensure_page("generate")
        host._generate_page._comfy = mock_comfy

        host.activate_route("train")
        assert host._current_route == "train"

        res = host.highlight_node("3")
        assert res is True
        assert host._current_route == "generate"
        mock_comfy.highlight_node.assert_called_once_with("3")


def test_bridge_preserves_json_looking_prompt_strings(q_app):
    bridge = ComfyBridge()
    sent = []
    bridge.sync_param_requested.connect(lambda _node, _widget, value: sent.append(value))
    for value in ("true", "123", "null", "[1,2]", '{"key":"value"}'):
        bridge.sync_param("1", "text", value)
        assert json.loads(sent[-1]) == value


def test_bridge_blocks_parameter_traffic_after_cross_origin_navigation(q_app):
    bridge = ComfyBridge(origin_check=lambda: False)
    sent, received = [], []
    bridge.sync_param_requested.connect(lambda *args: sent.append(args))
    bridge.param_changed_in_graph.connect(lambda *args: received.append(args))
    bridge.sync_param("1", "text", "private")
    bridge.notifyParamChanged("1", "text", '"remote"')
    assert not sent and not received


def test_mock_frontend_webengine_integration(q_app):
    """Validate bridge behavior against a live running ComfyUI frontend structure (#755)."""
    html_page = """<!DOCTYPE html>
<html>
<head>
  <script type="module">
    import { app } from "./scripts/app.js";
    window.app = app;
  </script>
</head>
<body><h1>ComfyUI Live Canvas</h1></body>
</html>"""

    app_module_js = """
let selectedNode = null;
const textWidget = { name: "ckpt_name", value: "initial_model.safetensors", callback(v) {} };
const imgWidget = { name: "image", value: "initial_pose.png", callback(v) {} };
const node1 = { id: 1, type: "CheckpointLoaderSimple", comfyClass: "CheckpointLoaderSimple",
                widgets: [textWidget], widgets_values: ["initial_model.safetensors"], inputs: [] };
const node9 = { id: 9, type: "LoadImage", comfyClass: "LoadImage",
                widgets: [imgWidget], widgets_values: ["initial_pose.png"], inputs: [] };
const graph = {
  _nodes: [node1, node9],
  getNodeById(id) { return this._nodes.find(n => String(n.id) === String(id)); },
  setDirtyCanvas() {}
};
const canvas = {
  canvas: { width: 800, height: 600 },
  ds: { scale: 1.0, offset: [0, 0] },
  selectNode(n) { selectedNode = n; }
};
export const app = { graph, canvas };
window.getTestSelectedNodeId = () => selectedNode ? selectedNode.id : null;
"""

    uploaded_files = []

    class MockFrontendHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html_page.encode("utf-8"))
            elif self.path == "/scripts/app.js":
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.end_headers()
                self.wfile.write(app_module_js.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/upload/image":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                uploaded_files.append(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"name": "server_synced_token.png"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockFrontendHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    view = QWebEngineView()
    url = f"http://127.0.0.1:{port}"
    try:
        channel, bridge = setup_comfy_web_channel(view, allowed_url=url)
        loop = QEventLoop()
        bridge.bridge_ready.connect(loop.quit)
        QTimer.singleShot(4000, loop.quit)
        view.load(QUrl(url))
        loop.exec()

        assert bridge.is_ready is True

        def spin(ms=250):
            lp = QEventLoop()
            QTimer.singleShot(ms, lp.quit)
            lp.exec()

        # 1. Bind matching template topology:
        bridge.bind_template({
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "9": {"class_type": "LoadImage", "inputs": {}},
        })
        spin(200)

        # 2. Highlight node 1
        bridge.highlight_node("1")
        spin(200)

        # 3. Synchronize parameter:
        bridge.sync_param("1", "ckpt_name", "updated_model.safetensors")
        spin(200)

        # 4. Set image node:
        bridge.set_image_node("9", "server_synced_token.png")
        spin(200)

        # 5. Verify values in browser DOM/JS
        result_js = {}

        def check_js(res):
            if res:
                result_js.update(json.loads(res))
            loop2.quit()

        loop2 = QEventLoop()
        view.page().runJavaScript(
            """JSON.stringify((() => {
                const g = window.app.graph;
                const n1 = g.getNodeById(1);
                const n9 = g.getNodeById(9);
                return {
                    node1_val: n1.widgets[0].value,
                    node9_val: n9.widgets[0].value,
                    selected: window.getTestSelectedNodeId()
                };
            })())""",
            check_js,
        )
        QTimer.singleShot(3000, loop2.quit)
        loop2.exec()

        assert result_js.get("node1_val") == "updated_model.safetensors"
        assert result_js.get("node9_val") == "server_synced_token.png"
        assert result_js.get("selected") == 1

        # 6. Test load_template into canvas
        loaded_events = []
        bridge.template_loaded.connect(loaded_events.append)
        bridge.load_template({
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "reloaded_ckpt.safetensors"}},
            "9": {"class_type": "LoadImage", "inputs": {"image": "reloaded_pose.png"}},
        })
        spin(200)
        assert loaded_events == [True]
    finally:
        view.page().setWebChannel(None)
        shiboken6.delete(view)
        q_app.processEvents()
        server.shutdown()
