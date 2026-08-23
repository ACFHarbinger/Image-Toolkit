"""Content Gen §1.4 (issue #35): ControlNet + IP-Adapter workflow wiring in
ComfyUITab (gui/src/tabs/models/gen/comfy_generate_tab.py).

Covers the new "ControlNet / IP-Adapter Workflow" panel: mode selection
(auto-filling the extra checkpoint default + image label per mode),
build_workflow()'s node-override wiring, and the queue-workflow handler's
guard rails (server-not-running, no-image-selected) plus its happy path
with the ComfyUIManager network calls mocked out.
"""

from unittest.mock import MagicMock, patch

import pytest

from gui.src.tabs.models.gen.comfy_generate_tab import (
    WORKFLOW_MODES,
    ComfyUITab,
    build_workflow,
)

pytestmark = pytest.mark.gui


@pytest.fixture
def tab(q_app):
    return ComfyUITab()


class TestModeSelection:
    def test_mode_combo_has_all_four_modes(self, tab):
        keys = [tab._mode_combo.itemData(i) for i in range(tab._mode_combo.count())]
        assert keys == [
            "controlnet_pose",
            "controlnet_depth",
            "controlnet_canny",
            "ipadapter_reference",
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
