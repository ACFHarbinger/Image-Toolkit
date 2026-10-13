"""Unit tests for ComfyBridge, comfy_bridge.js injection, and parameter sync (#755)."""
from unittest.mock import MagicMock

import pytest
from backend.src.constants.comfy import ServerState

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
        assert requested == [("1", "ckpt_name", "v1-5-pruned.safetensors")]

        # Test object/numeric serialization
        bridge.sync_param(3, "cfg", 7.5)
        assert requested[-1] == ("3", "cfg", "7.5")

    def test_set_image_node_emits_signal(self, q_app):
        bridge = ComfyBridge()
        requested = []
        bridge.set_image_requested.connect(lambda nid, img: requested.append((nid, img)))
        bridge.set_image_node(9, "pose.png")
        assert requested == [("9", "pose.png")]

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
        from PySide6.QtWebEngineWidgets import QWebEngineView

        view = QWebEngineView()
        channel, bridge = setup_comfy_web_channel(view)

        assert bridge is not None
        assert channel is not None
        assert "comfyBridge" in channel.registeredObjects()
        scripts = view.page().scripts().toList()
        assert any(s.name() == "comfy_bridge" for s in scripts)


class TestComfyUITabBridge:
    @pytest.fixture
    def tab(self, q_app):
        manager = MagicMock(state=ServerState.STOPPED, owns_server=False, port=8188, url="http://127.0.0.1:8188")
        controller = ComfyWorkspaceController(manager=manager)
        widget = ComfyUITab(controller=controller)
        yield widget
        widget.close()
        controller.shutdown()

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

        tab._on_param_changed_from_graph("9", "image", "/path/to/pose.png")
        assert tab._image_edit.text() == "/path/to/pose.png"

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

        tab._image_edit.setText("/tmp/ref.png")
        mock_bridge.sync_param.assert_any_call("9", "image", "/tmp/ref.png")

    def test_mode_switch_syncs_all_parameters(self, tab):
        mock_bridge = MagicMock()
        tab._bridge = mock_bridge

        idx = tab._mode_combo.findData("ipadapter_reference")
        tab._mode_combo.setCurrentIndex(idx)

        # ipadapter_reference: checkpoint_node: 1, positive_node: 6, negative_node: 7, extra_node: 3 (ipadapter_file)
        mock_bridge.sync_param.assert_any_call("1", "ckpt_name", tab._base_ckpt_edit.text().strip())
        mock_bridge.sync_param.assert_any_call("6", "text", tab._prompt_edit.text())
        mock_bridge.sync_param.assert_any_call("7", "text", tab._negative_prompt_edit.text())
        mock_bridge.sync_param.assert_any_call("3", "ipadapter_file", tab._extra_ckpt_edit.text().strip())


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
