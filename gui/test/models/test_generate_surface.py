"""Guided | Graph surface and matrix sweeps (#739, #740)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from backend.src.constants.comfy import ServerState
from PySide6.QtWidgets import QPushButton, QWidget

from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
from gui.src.tabs.models.gen.generate_surface import GenerateSurface, MatrixJob

pytestmark = pytest.mark.gui


@pytest.fixture
def surface(q_app):
    manager = MagicMock(
        state=ServerState.STOPPED,
        owns_server=False,
        port=8188,
        url="http://127.0.0.1:8188",
    )
    manager.runs.return_value = ()
    manager.get_object_info.return_value = None
    controller = ComfyWorkspaceController(manager=manager)
    widget = GenerateSurface(controller=controller)
    yield widget
    widget.close()
    controller.shutdown()


def test_mode_switch_keeps_prompt_image_and_graph_draft(surface):
    surface.guided._prompt_edit.setText("kept prompt")
    surface.guided._image_edit.setText("/tmp/kept.png")
    surface.set_mode("graph")
    surface.graph.editor.setPlainText('{"1": {"class_type": "KSampler", "inputs": {}}}')
    assert surface.graph.dirty
    surface.set_mode("guided")
    assert surface.guided._prompt_edit.text() == "kept prompt"
    assert surface.guided._image_edit.text() == "/tmp/kept.png"
    surface.set_mode("graph")
    assert surface.graph.editor.toPlainText().startswith('{"1"')
    assert surface.graph.dirty

    record = SimpleNamespace(
        prompt_id="other",
        workflow={"9": {"class_type": "SaveImage", "inputs": {}}},
        outputs=(),
        surface_mode="graph",
        status="Completed",
    )
    surface._filmstrip.upsert(record)
    surface._filmstrip._choose("other")
    assert surface.graph.load_record(record) is False
    assert "Unsaved graph edits were kept." in surface.graph.error.text()
    assert surface.graph.editor.toPlainText().startswith('{"1"')


def test_graph_unknown_override_is_visible_and_does_not_rewrite_the_draft(surface):
    draft = '{"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}'
    surface.set_mode("graph")
    surface.graph.editor.setPlainText(draft)
    surface.graph.overrides.setText('{"999": {"seed": 4}}')
    surface._on_queue_graph()
    assert "999" in surface.graph.error.text()
    assert surface.graph.editor.toPlainText() == draft
    surface._manager.queue_workflow.assert_not_called()


def test_filmstrip_shows_guided_runs_and_matrix_grid(surface):
    surface._controller.run_record_changed.emit(SimpleNamespace(
        prompt_id="g1",
        status="Completed",
        surface_mode="guided",
        outputs=(SimpleNamespace(filename="cat.png", subfolder=""),),
        sweep_axis=None,
    ))
    assert surface.findChild(QPushButton, "filmstrip_g1") is not None
    surface._filmstrip.upsert(SimpleNamespace(
        prompt_id="m0", status="Completed", surface_mode="matrix",
        parent_prompt_id=None, sweep_axis="seed", sweep_value="1", outputs=(),
    ))
    surface._filmstrip.upsert(SimpleNamespace(
        prompt_id="m1", status="Completed", surface_mode="matrix",
        parent_prompt_id="m0", sweep_axis="seed", sweep_value="2", outputs=(),
    ))
    grid = surface.findChild(QWidget, "matrix_grid_m0")
    assert grid is not None
    assert grid.findChild(QPushButton, "filmstrip_m1") is not None


def test_matrix_button_rejects_two_values_without_queueing(surface):
    surface.set_mode("matrix")
    surface._values.setText("1, 2")
    surface._on_matrix_queue()
    assert "3" in surface._matrix_message.text()
    surface._manager.upload_image.assert_not_called()


def test_matrix_job_queues_three_cells_and_promote_uses_full_size(surface):
    surface._manager.upload_image.return_value = "uploaded.png"
    ids = iter(["c0", "c1", "c2", "promoted"])

    def _queue(workflow, run_meta=None):
        _queue.calls.append((workflow, run_meta))
        return next(ids)

    _queue.calls = []
    surface._manager.queue_workflow.side_effect = _queue
    surface.guided._image_edit.setText("/tmp/pose.png")
    surface.guided._width_spin.setValue(1024)
    surface.guided._height_spin.setValue(1024)
    message = surface._run_matrix_job(MatrixJob(
        mode="controlnet_pose",
        image_path="/tmp/pose.png",
        base_checkpoint="sd_xl_base_1.0.safetensors",
        extra_checkpoint="control_v11p_sd15_openpose.pth",
        positive_prompt="a cat",
        negative_prompt="lowres",
        seed=0,
        width=1024,
        height=1024,
        axis="seed",
        values=(1, 2, 3),
    ), pressure_check=lambda: False)
    assert message.startswith("Queued 3 cells")
    assert _queue.calls[0][1]["surface_mode"] == "matrix"
    assert _queue.calls[0][0]["4"]["inputs"]["width"] == 512
    assert _queue.calls[2][1]["parent_prompt_id"] == "c0"
    assert _queue.calls[2][0]["5"]["inputs"]["seed"] == 3

    cell = _queue.calls[1][0]
    surface._filmstrip.upsert(SimpleNamespace(
        prompt_id="c1",
        workflow=cell,
        template_name="controlnet_generate.json",
        surface_mode="matrix",
        status="Completed",
        outputs=(),
    ))
    surface._filmstrip._choose("c1")
    surface._manager.state = ServerState.READY
    surface._queue_promoted(cell, 1024, 1280, "c1", "controlnet_generate.json")
    promoted, meta = _queue.calls[3]
    assert promoted["4"]["inputs"]["width"] == 1024
    assert promoted["4"]["inputs"]["height"] == 1280
    assert meta["surface_mode"] == "promoted"
    assert meta["parent_prompt_id"] == "c1"


def test_lora_axis_on_controlnet_template_is_visible(surface):
    surface._manager.upload_image.return_value = "uploaded.png"
    message = surface._run_matrix_job(MatrixJob(
        mode="controlnet_pose",
        image_path="/tmp/pose.png",
        base_checkpoint="base.safetensors",
        extra_checkpoint="cn.pth",
        positive_prompt="p",
        negative_prompt="n",
        seed=0,
        width=1024,
        height=1024,
        axis="lora_weight",
        values=(0.2, 0.5, 0.8),
    ))
    assert "LoraLoader" in message
    surface._manager.queue_workflow.assert_not_called()
