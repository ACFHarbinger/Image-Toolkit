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
    fetch_comfy_view,
    gpu_lease,
    parse_graph_submission,
    prepare_sweep,
    promote_cell,
    run_matrix_sweep,
    thermal_pressure,
    try_admit,
)
from backend.src.models.core.comfy_manager import ComfyUIManager


@pytest.fixture(autouse=True)
def _no_live_thermal_sensor(monkeypatch):
    monkeypatch.setattr("backend.src.comfy_matrix.read_gpu_temperature_c", lambda: None)


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
        wait_for_completion=lambda _pid: True,
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
        wait_for_completion=lambda _pid: True,
        workflow=_controlnet(),
        axis="controlnet_strength",
        values=[0.2, 0.5, 0.8],
        queue=lambda _workflow, _meta: "only",
        pressure_check=lambda: True,
        lease=lease,
    )
    assert result.prompt_ids == ()
    assert result.stopped == "pressure"
    assert lease.try_acquire("next")
    lease.release("next")


def test_sweep_stop_flag_and_missing_axis():
    lease = GpuLease()
    stopped = run_matrix_sweep(
        wait_for_completion=lambda _pid: True,
        workflow=_controlnet(),
        axis="cfg",
        values=[4.0, 5.0, 6.0],
        queue=lambda _workflow, _meta: "x",
        stop_check=lambda: True,
        pressure_check=lambda: False,
        lease=lease,
    )
    assert stopped.stopped == "stop"
    assert stopped.prompt_ids == ()

    with pytest.raises(Exception, match="LoraLoader"):
        run_matrix_sweep(
            wait_for_completion=lambda _pid: True,
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
        wait_for_completion=lambda _pid: True,
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
        wait_for_completion=lambda _pid: True,
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


def test_sweep_waits_for_execution_and_keeps_lease():
    lease = GpuLease()
    events = []

    def queue(workflow, meta):
        prompt_id = str(workflow["5"]["inputs"]["seed"])
        events.append(("queue", prompt_id))
        return prompt_id

    def wait(prompt_id):
        assert not lease.try_acquire("other")
        events.append(("finish", prompt_id))
        return prompt_id != "2"

    result = run_matrix_sweep(
        workflow=_controlnet(), axis="seed", values=[1, 2, 3], queue=queue,
        wait_for_completion=wait, pressure_check=lambda: False, lease=lease,
    )
    assert events == [("queue", "1"), ("finish", "1"), ("queue", "2"), ("finish", "2")]
    assert result.stopped == "execution"
    assert lease.try_acquire("after")


@pytest.mark.parametrize("overrides", ['{"1": []}', '{"1": {"seed": 2}}'])
def test_malformed_graph_inputs_are_visible_errors(overrides):
    with pytest.raises(ValueError, match="must be objects"):
        parse_graph_submission('{"1": {"inputs": []}}', overrides)


def test_stop_waits_for_current_cell_before_releasing_lease():
    import threading

    lease = GpuLease()
    running = threading.Event()
    finish = threading.Event()
    stop = threading.Event()
    queued = []
    results = []

    def wait(_prompt_id):
        running.set()
        assert finish.wait(2)
        return True

    def run():
        results.append(run_matrix_sweep(
            workflow=_controlnet(), axis="seed", values=[1, 2, 3],
            queue=lambda _graph, _meta: queued.append("cell") or "cell",
            wait_for_completion=wait, stop_check=stop.is_set,
            pressure_check=lambda: False, lease=lease,
        ))

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert running.wait(1)
        stop.set()
        assert not lease.try_acquire("other")
        assert queued == ["cell"]
    finally:
        finish.set()
        worker.join(2)
    assert not worker.is_alive()
    assert results[0].stopped == "stop"
    assert queued == ["cell"]
    assert lease.try_acquire("after")


def test_thermal_stop_runs_before_the_next_cell_and_releases():
    lease = GpuLease()
    readings = iter([False, True])
    result = run_matrix_sweep(
        wait_for_completion=lambda _pid: True,
        workflow=_controlnet(),
        axis="seed",
        values=[1, 2, 3],
        queue=lambda _workflow, _meta: "hot",
        pressure_check=lambda: False,
        thermal_check=lambda: next(readings),
        lease=lease,
    )
    assert result.prompt_ids == ("hot",)
    assert result.stopped == "thermal"
    assert lease.try_acquire("after")
    lease.release("after")


def test_thermal_signal_ignores_a_missing_or_cool_sensor():
    assert thermal_pressure(lambda: None) is False
    assert thermal_pressure(lambda: 40) is False
    assert thermal_pressure(lambda: float("nan")) is False
    assert thermal_pressure(lambda: 85) is True


def test_shared_admission_is_not_machine_wide():
    lease = GpuLease()
    lease.note_external_browser(True)
    assert lease.machine_wide is False
    assert "browser" in lease.scope_text().lower()
    assert try_admit("lora-train", lease) is None
    assert try_admit("matrix", lease) == "GPU admission is held by lora-train."
    lease.release("lora-train")
    assert try_admit("matrix", lease) is None
    lease.release("matrix")


def test_lora_template_sweeps_strength_model():
    workflow = ComfyUIManager.load_workflow("lora_generate.json")
    captured = []

    def queue(cell, _meta):
        captured.append(cell)
        return f"p{len(captured)}"

    result = run_matrix_sweep(
        wait_for_completion=lambda _pid: True,
        workflow=workflow,
        axis="lora_weight",
        values=[0.2, 0.5, 0.8],
        queue=queue,
        preview_edge=512,
        pressure_check=lambda: False,
        thermal_check=lambda: False,
        lease=GpuLease(),
    )
    assert result.stopped is None
    assert captured[0]["2"]["inputs"]["strength_model"] == 0.2
    assert captured[2]["2"]["inputs"]["strength_model"] == 0.8
    assert captured[0]["5"]["inputs"]["width"] == 512
    assert "LoraLoader" in workflow["2"]["class_type"]


def test_fetch_view_requests_the_output_bytes(monkeypatch):
    seen = {}

    class _Body:
        def read(self, limit):
            seen["limit"] = limit
            return b"png-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def _open(url, timeout=0):
        seen["url"] = url
        seen["timeout"] = timeout
        return _Body()

    monkeypatch.setattr("urllib.request.urlopen", _open)
    assert fetch_comfy_view("http://127.0.0.1:8188", "cat.png", "out") == b"png-bytes"
    assert seen["url"].endswith("/view?filename=cat.png&subfolder=out&type=output&preview=webp%3B80")
    assert seen["limit"] == 2_000_001
    assert gpu_lease.machine_wide is False
