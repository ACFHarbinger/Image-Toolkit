"""Matrix sweeps and strict workflow overrides (#739, #740)."""
from __future__ import annotations

import pytest

from backend.src.comfy_matrix import (
    CELL_CAP,
    GpuLease,
    SweepResult,
    UnknownWorkflowNodeError,
    apply_node_overrides,
    check_cell_count,
    parse_graph_submission,
    prepare_sweep,
    promote_cell,
    run_matrix_sweep,
)
from backend.src.models.core.comfy_manager import ComfyUIManager


def _controlnet() -> dict:
    return ComfyUIManager.load_workflow("controlnet_generate.json")


def test_unknown_node_override_names_the_id():
    with pytest.raises(UnknownWorkflowNodeError, match="999") as caught:
        apply_node_overrides(_controlnet(), {"999": {"seed": 1}})
    assert caught.value.node_ids == ["999"]


def test_apply_override_keeps_other_inputs():
    workflow = apply_node_overrides(_controlnet(), {"5": {"seed": 7}})
    assert workflow["5"]["inputs"]["seed"] == 7
    assert workflow["5"]["inputs"]["steps"] == 25
    assert workflow["5"]["inputs"]["cfg"] == 6.0


def test_prepare_sweep_rejects_short_and_long_lists():
    values, message = prepare_sweep("seed", "1, 2")
    assert values is None
    assert "3" in message and "9" in message
    values, message = prepare_sweep("cfg", "1, 2, 3, 4, 5, 6, 7, 8, 9, 10")
    assert values is None
    assert "10" in message
    assert check_cell_count(CELL_CAP + 1)


def test_prepare_sweep_accepts_three_seeds():
    values, message = prepare_sweep("seed", "1, 2, 3")
    assert values == [1, 2, 3]
    assert "3 cells" in message
    assert str(CELL_CAP) in message


def test_graph_override_unknown_node_is_an_error():
    text = '{"1": {"class_type": "KSampler", "inputs": {"seed": 0}}}'
    with pytest.raises(UnknownWorkflowNodeError, match="999"):
        parse_graph_submission(text, '{"999": {"seed": 1}}')


def test_sweep_queues_each_value_under_one_parent():
    captured = []

    def queue(workflow, meta):
        captured.append((workflow, meta))
        return f"c{len(captured) - 1}"

    result = run_matrix_sweep(
        workflow=_controlnet(),
        axis="seed",
        values=[1, 2, 3],
        queue=queue,
        template_name="controlnet_generate.json",
        preview_edge=512,
        pressure_check=lambda: False,
        lease=GpuLease(),
    )
    assert result == SweepResult(("c0", "c1", "c2"), "c0", None)
    assert [item[1]["sweep_value"] for item in captured] == ["1", "2", "3"]
    assert captured[0][1]["parent_prompt_id"] is None
    assert captured[1][1]["parent_prompt_id"] == "c0"
    assert captured[2][1]["parent_prompt_id"] == "c0"
    assert captured[0][0]["5"]["inputs"]["seed"] == 1
    assert captured[2][0]["4"]["inputs"]["width"] == 512
    assert captured[2][0]["5"]["inputs"]["steps"] == 25


def test_sweep_stops_between_cells_on_pressure_and_releases_the_lease():
    lease = GpuLease()
    result = run_matrix_sweep(
        workflow=_controlnet(),
        axis="controlnet_strength",
        values=[0.2, 0.5, 0.8],
        queue=lambda _workflow, _meta: "only",
        pressure_check=lambda: True,
        lease=lease,
    )
    assert result.prompt_ids == ("only",)
    assert result.stopped == "pressure"
    assert lease.try_acquire("next")
    lease.release("next")


def test_sweep_stop_flag_and_missing_axis():
    lease = GpuLease()
    stopped = run_matrix_sweep(
        workflow=_controlnet(),
        axis="cfg",
        values=[4.0, 5.0, 6.0],
        queue=lambda _workflow, _meta: "x",
        stop_check=lambda: True,
        pressure_check=lambda: False,
        lease=lease,
    )
    assert stopped.stopped == "stop"
    assert stopped.prompt_ids == ("x",)

    with pytest.raises(Exception, match="LoraLoader"):
        run_matrix_sweep(
            workflow=_controlnet(),
            axis="lora_weight",
            values=[0.2, 0.5, 0.8],
            queue=lambda _workflow, _meta: "nope",
            pressure_check=lambda: False,
            lease=lease,
        )
    assert lease.try_acquire("after-error")


def test_cap_refuses_before_queue():
    queued = []
    result = run_matrix_sweep(
        workflow=_controlnet(),
        axis="steps",
        values=list(range(CELL_CAP + 1)),
        queue=lambda workflow, meta: queued.append(workflow) or "x",
        lease=GpuLease(),
    )
    assert result.stopped == "cap"
    assert queued == []


def test_promote_restores_full_latent_size():
    preview = promote_cell(_controlnet(), full_width=512, full_height=512)
    assert preview["4"]["inputs"]["width"] == 512
    full = promote_cell(preview, full_width=1024, full_height=1280)
    assert full["4"]["inputs"]["width"] == 1024
    assert full["4"]["inputs"]["height"] == 1280
    assert full["5"]["inputs"]["seed"] == preview["5"]["inputs"]["seed"]


def test_second_lease_holder_is_refused():
    lease = GpuLease()
    assert lease.try_acquire("matrix")
    blocked = run_matrix_sweep(
        workflow=_controlnet(),
        axis="seed",
        values=[1, 2, 3],
        queue=lambda _workflow, _meta: "x",
        lease=lease,
        pressure_check=lambda: False,
    )
    assert blocked.stopped == "lease"
    assert blocked.prompt_ids == ()
    lease.release("matrix")
