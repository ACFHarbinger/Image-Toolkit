"""Content Gen §1.4 (issue #35): ControlNet + IP-Adapter workflow wiring in
ComfyUITab (gui/src/tabs/models/gen/comfy_generate_tab.py).

Covers the new "ControlNet / IP-Adapter Workflow" panel: mode selection
(auto-filling the extra checkpoint default + image label per mode),
build_workflow()'s node-override wiring, and the queue-workflow handler's
guard rails (server-not-running, no-image-selected) plus its happy path
with the ComfyUIManager network calls mocked out.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from backend.src.constants.comfy import ServerState

from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
from gui.src.tabs.models.gen.comfy_generate_tab import (
    WORKFLOW_MODES,
    ComfyUITab,
    build_workflow,
)

pytestmark = pytest.mark.gui


@pytest.fixture
def tab(q_app):
    manager = MagicMock(state=ServerState.STOPPED, owns_server=False, port=8188, url="http://127.0.0.1:8188")
    controller = ComfyWorkspaceController(manager=manager)
    widget = ComfyUITab(controller=controller)
    yield widget
    widget.close()
    controller.shutdown()
    q_app.processEvents()


class TestModeSelection:
    def test_mode_combo_lists_guided_workflows(self, tab):
        keys = [tab._mode_combo.itemData(i) for i in range(tab._mode_combo.count())]
        assert keys == [
            "controlnet_pose",
            "controlnet_depth",
            "controlnet_canny",
            "ipadapter_reference",
            "lora",
        ]

    def test_default_mode_prefills_pose_controlnet_checkpoint(self, tab):
        assert tab._mode_combo.currentData() == "controlnet_pose"
        assert tab._extra_ckpt_edit.text() == "control_v11p_sd15_openpose.pth"
        assert tab._image_label.text() == "Pose Control Image:"

    def test_switching_to_ipadapter_updates_extra_fields(self, tab):
        idx = tab._mode_combo.findData("ipadapter_reference")
        tab._mode_combo.setCurrentIndex(idx)
        assert tab._extra_ckpt_edit.text() == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert tab._image_label.text() == "Reference Image:"
        assert tab._extra_ckpt_label.text() == "IP-Adapter Checkpoint:"

    def test_switching_to_depth_and_canny_updates_defaults(self, tab):
        idx = tab._mode_combo.findData("controlnet_depth")
        tab._mode_combo.setCurrentIndex(idx)
        assert tab._extra_ckpt_edit.text() == "control_v11f1p_sd15_depth.pth"

        idx = tab._mode_combo.findData("controlnet_canny")
        tab._mode_combo.setCurrentIndex(idx)
        assert tab._extra_ckpt_edit.text() == "control_v11p_sd15_canny.pth"


class TestBuildWorkflow:
    def test_controlnet_mode_wires_prompts_checkpoint_and_control_image(self):
        workflow = build_workflow(
            "controlnet_pose",
            base_checkpoint="my_base.safetensors",
            extra_checkpoint="my_controlnet.pth",
            positive_prompt="a cat",
            negative_prompt="lowres",
            image_filename="uploaded_pose.png",
        )
        assert workflow["1"]["inputs"]["ckpt_name"] == "my_base.safetensors"
        assert workflow["2"]["inputs"]["text"] == "a cat"
        assert workflow["3"]["inputs"]["text"] == "lowres"
        assert workflow["8"]["inputs"]["control_net_name"] == "my_controlnet.pth"
        assert workflow["9"]["inputs"]["image"] == "uploaded_pose.png"

    def test_ipadapter_mode_wires_prompts_checkpoint_and_reference_image(self):
        workflow = build_workflow(
            "ipadapter_reference",
            base_checkpoint="my_base.safetensors",
            extra_checkpoint="my_ipadapter.safetensors",
            positive_prompt="a dog",
            negative_prompt="blurry",
            image_filename="uploaded_ref.png",
        )
        assert workflow["1"]["inputs"]["ckpt_name"] == "my_base.safetensors"
        assert workflow["6"]["inputs"]["text"] == "a dog"
        assert workflow["7"]["inputs"]["text"] == "blurry"
        assert workflow["3"]["inputs"]["ipadapter_file"] == "my_ipadapter.safetensors"
        assert workflow["4"]["inputs"]["image"] == "uploaded_ref.png"

    @pytest.mark.parametrize("mode", list(WORKFLOW_MODES))
    def test_every_mode_builds_without_error(self, mode):
        workflow = build_workflow(
            mode,
            base_checkpoint="base.safetensors",
            extra_checkpoint="extra.safetensors",
            positive_prompt="p",
            negative_prompt="n",
            image_filename="img.png",
        )
        assert workflow


class TestQueueWorkflowHandler:
    def test_queue_blocked_when_server_not_running(self, tab):
        tab._manager = MagicMock(is_running=False)
        tab._image_edit.setText("/tmp/some_control.png")

        logs = []
        tab._log_signal.connect(lambda line: logs.append(line))
        tab._on_queue_workflow_clicked()

        assert any("server is not running" in line for line in logs)
        tab._manager.upload_image.assert_not_called()

    def test_queue_blocked_when_no_image_selected(self, tab):
        tab._controller.manager.state = ServerState.READY
        tab._manager = MagicMock(is_running=True)
        tab._image_edit.setText("")

        logs = []
        tab._log_signal.connect(lambda line: logs.append(line))
        tab._on_queue_workflow_clicked()

        assert any("No control/reference image" in line for line in logs)
        tab._manager.upload_image.assert_not_called()

    def test_queue_worker_happy_path_uploads_and_queues(self, tab):
        tab._manager = MagicMock(is_running=True)
        tab._manager.upload_image.return_value = "uploaded_control.png"
        tab._manager.queue_workflow.return_value = "prompt-xyz"

        logs = []
        tab._log_signal.connect(lambda line: logs.append(line))

        tab._queue_workflow_worker(
            "controlnet_canny",
            "/tmp/canny.png",
            "base.safetensors",
            "control_v11p_sd15_canny.pth",
            "prompt text",
            "neg text",
        )

        tab._manager.upload_image.assert_called_once_with("/tmp/canny.png")
        assert tab._manager.queue_workflow.call_count == 1
        submitted_workflow = tab._manager.queue_workflow.call_args[0][0]
        assert submitted_workflow["9"]["inputs"]["image"] == "uploaded_control.png"
        assert any("prompt_id=prompt-xyz" in line for line in logs)

    def test_queue_worker_logs_error_on_exception(self, tab):
        tab._manager = MagicMock(is_running=True)
        tab._manager.upload_image.side_effect = RuntimeError("boom")

        logs = []
        tab._log_signal.connect(lambda line: logs.append(line))

        tab._queue_workflow_worker(
            "controlnet_pose", "/tmp/x.png", "base.safetensors", "cn.pth", "p", "n"
        )

        assert any("Error: boom" in line for line in logs)


class TestBrowseImage:
    def test_browse_sets_image_edit_text_on_selection(self, tab):
        with patch(
            "gui.src.tabs.models.gen.comfy_generate_tab.QFileDialog.getOpenFileName",
            return_value=("/tmp/chosen.png", "Images"),
        ):
            tab._on_browse_image()
        assert tab._image_edit.text() == "/tmp/chosen.png"

    def test_browse_leaves_image_edit_unchanged_on_cancel(self, tab):
        tab._image_edit.setText("/tmp/existing.png")
        with patch(
            "gui.src.tabs.models.gen.comfy_generate_tab.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            tab._on_browse_image()
        assert tab._image_edit.text() == "/tmp/existing.png"

    def test_browse_uses_non_native_dialog(self, tab):
        """#728: native QFileDialog is this app's documented crash class."""
        from PySide6.QtWidgets import QFileDialog

        with patch(
            "gui.src.tabs.models.gen.comfy_generate_tab.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ) as mock_dialog:
            tab._on_browse_image()
        assert (
            mock_dialog.call_args.kwargs["options"]
            == QFileDialog.Option.DontUseNativeDialog
        )


class TestPreFlightValidation:
    """#738: Queue button reflects validate_template() per guided mode."""

    def _issue(self, message, node_id="8", input_name="control_net_name"):
        # Duck-typed stand-in for backend TemplateIssue (gui/test conftest
        # mocks backend.src.models.core.*, so the real dataclass can't load).
        return SimpleNamespace(
            node_id=node_id, input_name=input_name,
            code="missing_file", message=message,
        )

    def _go_ready(self, tab, *, object_info, issues=()):
        manager = tab._controller.manager
        manager.state = ServerState.READY
        manager.get_object_info.return_value = object_info
        manager.validate_template.return_value = list(issues)
        tab._controller.server_state_changed.emit(ServerState.READY)

    def test_queue_waits_while_object_info_pending(self, tab):
        self._go_ready(tab, object_info=None)
        assert not tab._queue_btn.isEnabled()
        assert tab._validation_label.text() == "Checking workflow compatibility…"

    def test_queue_ready_when_no_issues(self, tab):
        self._go_ready(tab, object_info={"KSampler": {}})
        tab._controller.object_info_changed.emit({"KSampler": {}})
        assert tab._queue_btn.isEnabled()
        assert tab._validation_label.text() == "Ready"

    def test_queue_blocked_with_missing_file_message(self, tab):
        issue = self._issue(
            "missing file 'never_downloaded.pth' (input 'control_net_name' of node '8')",
            node_id="8",
        )
        self._go_ready(tab, object_info={"ControlNetLoader": {}}, issues=[issue])
        tab._controller.object_info_changed.emit({"ControlNetLoader": {}})
        assert not tab._queue_btn.isEnabled()
        assert tab._validation_label.text().startswith("missing file")
        assert issue.message in tab._queue_btn.toolTip()

    def test_multiple_issues_label_counts_the_rest(self, tab):
        issues = [
            self._issue("missing file 'a.pth'"),
            self._issue("missing file 'b.safetensors'", node_id="1", input_name="ckpt_name"),
        ]
        self._go_ready(tab, object_info={"x": {}}, issues=issues)
        tab._controller.object_info_changed.emit({"x": {}})
        assert tab._validation_label.text() == "missing file 'a.pth' (+1 more)"

    def test_fetch_failure_fails_open(self, tab):
        self._go_ready(tab, object_info=None)
        tab._controller.object_info_changed.emit(None)
        assert tab._queue_btn.isEnabled()
        assert tab._validation_label.text() == ""
        assert "Pre-flight validation unavailable" in tab._log_view.toPlainText()

    def test_mode_switch_revalidates_with_mode_defaults(self, tab):
        self._go_ready(tab, object_info={"x": {}})
        tab._controller.object_info_changed.emit({"x": {}})
        assert tab._queue_btn.isEnabled()

        tab._controller.manager.validate_template.return_value = [self._issue("missing file 'x'")]
        idx = tab._mode_combo.findData("ipadapter_reference")
        tab._mode_combo.setCurrentIndex(idx)

        assert not tab._queue_btn.isEnabled()
        assert tab._validation_label.text() == "missing file 'x'"
        validated = tab._controller.manager.validate_template.call_args[0][0]
        assert validated["3"]["inputs"]["ipadapter_file"] == "ip-adapter-plus_sdxl_vit-h.safetensors"

    def test_base_checkpoint_edit_revalidates_all_modes(self, tab):
        self._go_ready(tab, object_info={"x": {}})
        tab._controller.object_info_changed.emit({"x": {}})
        tab._controller.manager.validate_template.reset_mock()
        tab._base_ckpt_edit.setText("animagine_xl.safetensors")
        assert tab._controller.manager.validate_template.call_count == len(WORKFLOW_MODES)

    def test_queue_click_blocked_when_issues_cached(self, tab):
        self._go_ready(tab, object_info={"x": {}}, issues=[self._issue("missing file 'a.pth'")])
        tab._controller.object_info_changed.emit({"x": {}})
        tab._image_edit.setText("/tmp/control.png")
        tab._controller.run_http_action = MagicMock()

        logs = []
        tab._log_signal.connect(logs.append)
        tab._on_queue_workflow_clicked()

        tab._controller.run_http_action.assert_not_called()
        assert any("Blocked by pre-flight validation" in line for line in logs)

    def test_leaving_ready_clears_cached_issues(self, tab):
        self._go_ready(tab, object_info={"x": {}}, issues=[self._issue("missing file 'a.pth'")])
        tab._controller.object_info_changed.emit({"x": {}})
        assert not tab._queue_btn.isEnabled()

        tab._controller.manager.state = ServerState.STOPPED
        tab._controller.server_state_changed.emit(ServerState.STOPPED)
        assert not tab._queue_btn.isEnabled()
        assert tab._validation_label.text() == ""
        assert tab._issues_by_mode == {}
