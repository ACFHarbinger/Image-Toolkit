"""Diff & Apply widget for validated guidance suggestions (#752)."""
import json
from pathlib import Path

import pytest
from middleware.src.core.guidance_schema import (
    parse_guidance_response,
    validate_guidance,
    workflow_hash,
)
from PySide6.QtWidgets import QPushButton

from gui.src.tabs.models.guidance_diff_widget import (
    GuidanceDiffWidget,
    build_patch,
    filtered_validation,
    write_variant_file,
)

pytestmark = pytest.mark.gui

_TEMPLATES = Path(__file__).resolve().parents[3] / "configs" / "comfy_workflows"


def _template(name="lora_generate.json"):
    return json.loads((_TEMPLATES / name).read_text())


def _validation(workflow, changes, swap=None):
    response = {
        "schema_version": 1,
        "workflow_hash": workflow_hash(workflow),
        "workflow_param_changes": changes,
        "model_swap": swap,
        "dataset_guidance": None,
    }
    parsed = parse_guidance_response(response)
    assert parsed.ok, parsed.errors
    return validate_guidance(parsed.response, workflow)


def _ok_validation(workflow=None):
    workflow = workflow if workflow is not None else _template()
    cfg = workflow["6"]["inputs"]["cfg"]
    return workflow, _validation(
        workflow,
        [{"node_id": "6", "input": "cfg", "from": cfg, "to": 9.0, "reason": "crisper subject"}],
    )


# ── Pure helpers ──────────────────────────────────────────────────────────


def test_write_variant_file_names_source_and_roundtrips(tmp_path):
    workflow = _template()
    path = write_variant_file(workflow, source_id="abc123", directory=str(tmp_path))
    assert Path(path).parent == tmp_path
    assert "abc123" in Path(path).name
    assert json.loads(Path(path).read_text()) == workflow


def test_write_variant_file_without_source_uses_workflow_name(tmp_path):
    path = write_variant_file(_template(), source_id=None, directory=str(tmp_path))
    assert Path(path).name.startswith("workflow_variant")


def test_filtered_validation_keeps_refusal_flags():
    workflow, validation = _ok_validation()
    assert not validation.stale and not validation.hallucination_flagged
    sub = filtered_validation(validation, [])
    assert sub.verdicts == ()
    assert sub.response is validation.response


def test_build_patch_applies_only_selected_rows():
    workflow = _template()
    cfg = workflow["6"]["inputs"]["cfg"]
    steps = workflow["6"]["inputs"]["steps"]
    validation = _validation(
        workflow,
        [
            {"node_id": "6", "input": "cfg", "from": cfg, "to": 9.0, "reason": "a"},
            {"node_id": "6", "input": "steps", "from": steps, "to": 30, "reason": "b"},
        ],
    )
    assert validation.ok
    patched = build_patch(workflow, validation, [validation.verdicts[0]])
    assert patched["6"]["inputs"]["cfg"] == 9.0
    assert patched["6"]["inputs"]["steps"] == steps
    assert workflow["6"]["inputs"]["cfg"] == cfg  # source never mutated


def test_build_patch_refuses_stale_batch():
    workflow, validation = _ok_validation()
    edited = json.loads(json.dumps(workflow))
    edited["6"]["inputs"]["cfg"] = 99.0
    stale = validate_guidance(validation.response, edited)
    assert stale.stale
    assert build_patch(edited, stale, list(stale.verdicts)) is None


# ── Widget rendering ──────────────────────────────────────────────────────


def test_widget_renders_one_row_per_verdict(q_app):
    workflow, validation = _ok_validation()
    widget = GuidanceDiffWidget()
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    try:
        assert len(widget.valid_toggles()) == 1
        assert widget.findChild(QPushButton, "guidance_requeue_btn") is not None
        assert widget._requeue_btn.isEnabled()
    finally:
        widget.deleteLater()


def test_widget_disables_requeue_on_hallucination(q_app):
    workflow = _template()
    cfg = workflow["6"]["inputs"]["cfg"]
    validation = _validation(
        workflow,
        [
            {"node_id": "6", "input": "cfg", "from": cfg, "to": 9.0, "reason": "good"},
            {"node_id": "6", "input": "steps", "from": "WRONG", "to": 30, "reason": "bad premise"},
        ],
    )
    assert validation.hallucination_flagged
    widget = GuidanceDiffWidget()
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    try:
        assert not widget._requeue_btn.isEnabled()
        assert "hallucination" in widget._banner.text().lower()
    finally:
        widget.deleteLater()


def test_widget_invalid_row_has_no_toggle_but_shows_reason(q_app):
    workflow = _template()
    validation = _validation(
        workflow,
        [{"node_id": "999", "input": "cfg", "from": 7, "to": 9.0, "reason": "ghost node"}],
    )
    assert not validation.ok
    widget = GuidanceDiffWidget()
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    try:
        assert widget.valid_toggles() == []
        assert any("999" in summary for summary in widget.summaries())
    finally:
        widget.deleteLater()


def test_widget_missing_asset_row_proposes_install_not_apply(q_app):
    workflow = _template()
    lora = workflow["2"]["inputs"]["lora_name"]
    validation = _validation(
        workflow,
        [],
        swap={"node_id": "2", "input": "lora_name", "from": lora, "to": "nope.safetensors", "reason": "try this"},
    )
    assert validation.verdicts and validation.verdicts[0].status == "missing_asset"
    widget = GuidanceDiffWidget()
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    from PySide6.QtWidgets import QLabel

    try:
        assert widget.valid_toggles() == []
        assert not widget._requeue_btn.isEnabled()
        assert any("lora_name" in summary for summary in widget.summaries())
        shown = " ".join(label.text() for label in widget.findChildren(QLabel))
        assert "install" in shown.lower()
    finally:
        widget.deleteLater()


# ── Re-queue ──────────────────────────────────────────────────────────────


def test_requeue_submits_patch_with_variant_meta(q_app, tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    workflow, validation = _ok_validation()
    manager = MagicMock()
    manager.queue_workflow.return_value = "new-pid-1"
    from middleware.src.constants.comfy import ServerState

    controller = MagicMock()
    controller.server_state = ServerState.READY
    controller.run_http_action.side_effect = lambda action: action() or True
    widget = GuidanceDiffWidget(controller=controller, manager=manager, variant_dir=str(tmp_path))
    widget.set_guidance(
        workflow=workflow, validation=validation, source_prompt_id="pid1", source_mode="guided"
    )
    try:
        queued = []
        widget.variant_queued.connect(queued.append)
        widget._on_requeue()
        assert queued == ["new-pid-1"]
        (patched,), kwargs = manager.queue_workflow.call_args
        meta = kwargs["run_meta"]
        assert patched["6"]["inputs"]["cfg"] == 9.0
        assert meta["parent_prompt_id"] == "pid1"
        assert meta["variant_label"] == "assistant-suggested"
        assert meta["surface_mode"] == "guided"
        written = list(tmp_path.glob("pid1_variant*.json"))
        assert len(written) == 1
        assert json.loads(written[0].read_text()) == patched
        traj = meta["guidance_trajectory"]
        assert traj["root_prompt_id"] == "pid1"
        assert traj["steps"][0]["applied"][0]["input_name"] == "cfg"
        assert traj["steps"][0]["applied"][0]["to"] == 9.0
        assert list(tmp_path.glob("*_trajectory.json"))
    finally:
        widget.deleteLater()


def test_requeue_refuses_without_server_ready(q_app):
    from unittest.mock import MagicMock

    from middleware.src.constants.comfy import ServerState

    workflow, validation = _ok_validation()
    controller = MagicMock()
    controller.server_state = ServerState.STOPPED
    widget = GuidanceDiffWidget(controller=controller, manager=MagicMock())
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    try:
        widget._on_requeue()
        widget._manager.queue_workflow.assert_not_called()
        assert "not running" in widget._status.text().lower()
    finally:
        widget.deleteLater()


def test_requeue_uses_only_checked_rows(q_app, tmp_path):
    from unittest.mock import MagicMock

    from middleware.src.constants.comfy import ServerState

    workflow = _template()
    cfg = workflow["6"]["inputs"]["cfg"]
    steps = workflow["6"]["inputs"]["steps"]
    validation = _validation(
        workflow,
        [
            {"node_id": "6", "input": "cfg", "from": cfg, "to": 9.0, "reason": "a"},
            {"node_id": "6", "input": "steps", "from": steps, "to": 30, "reason": "b"},
        ],
    )
    manager = MagicMock()
    manager.queue_workflow.return_value = "new-pid-2"
    controller = MagicMock()
    controller.server_state = ServerState.READY
    controller.run_http_action.side_effect = lambda action: action() or True
    widget = GuidanceDiffWidget(controller=controller, manager=manager, variant_dir=str(tmp_path))
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="pid1")
    try:
        toggles = widget.valid_toggles()
        assert len(toggles) == 2
        toggles[1].setChecked(False)
        widget._on_requeue()
        (patched,), _kwargs = manager.queue_workflow.call_args
        assert patched["6"]["inputs"]["cfg"] == 9.0
        assert patched["6"]["inputs"]["steps"] == steps
    finally:
        widget.deleteLater()


# ── Review/host wiring ──────────────────────────────────────────────────


def test_review_page_hosts_guidance_widget(q_app):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage
    from gui.src.tabs.models.guidance_diff_widget import GuidanceDiffWidget

    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    try:
        widget = page.findChild(GuidanceDiffWidget, "dl_guidance_diff")
        assert widget is not None
        assert page.findChild(QPushButton, "dl_guidance_load_btn") is not None
        workflow, validation = _ok_validation()
        page.show_guidance(workflow=workflow, validation=validation, source_prompt_id="pid9")
        assert len(widget.valid_toggles()) == 1
    finally:
        page.deleteLater()


def test_review_load_button_needs_generate_selection(q_app):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    host = MagicMock()
    host.generate_selection.return_value = None
    page = _ReviewToolsPage(host=host, preference_store=None)
    try:
        page._on_load_generate_selection()
        assert "filmstrip" in page._guidance._status.text()
    finally:
        page.deleteLater()


def test_review_load_button_uses_generate_selection(q_app):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    workflow = _template()
    host = MagicMock()
    host.generate_selection.return_value = ("pid7", workflow, "guided")
    page = _ReviewToolsPage(host=host, preference_store=None)
    try:
        page._on_load_generate_selection()
        assert page._guidance._source_id == "pid7"
        assert "validated suggestions" in page._guidance._status.text().lower()
    finally:
        page.deleteLater()


def test_host_generate_selection_needs_workflow_dict():
    from types import SimpleNamespace

    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

    host = DeepLearningWorkspaceHost.__new__(DeepLearningWorkspaceHost)
    strip = SimpleNamespace(
        selected_record=lambda: SimpleNamespace(prompt_id="x", workflow=None)
    )
    host._pages = {
        "generate": SimpleNamespace(_comfy_surface=SimpleNamespace(_filmstrip=strip))
    }
    assert host.generate_selection() is None


def test_host_generate_selection_returns_triple():
    from types import SimpleNamespace

    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

    workflow = {"6": {"inputs": {"cfg": 7}}}
    record = SimpleNamespace(prompt_id="pid3", workflow=workflow, surface_mode="graph")
    strip = SimpleNamespace(selected_record=lambda: record)
    host = DeepLearningWorkspaceHost.__new__(DeepLearningWorkspaceHost)
    host._pages = {
        "generate": SimpleNamespace(_comfy_surface=SimpleNamespace(_filmstrip=strip))
    }
    assert host.generate_selection() == ("pid3", workflow, "graph")


def test_filmstrip_cell_shows_variant_label(q_app):
    from types import SimpleNamespace

    from gui.src.tabs.models.gen.generate_surface import _cell_text

    record = SimpleNamespace(
        prompt_id="new-pid",
        status="success",
        outputs=(),
        surface_mode="guided",
        variant_label="assistant-suggested",
    )
    assert "[assistant-suggested]" in _cell_text(record)


def test_variant_paths_are_unique_and_contained(tmp_path):
    first = Path(write_variant_file({"a": 1}, source_id="../escape", directory=str(tmp_path)))
    second = Path(write_variant_file({"a": 2}, source_id="../escape", directory=str(tmp_path)))
    assert first.parent == second.parent == tmp_path
    assert first != second
    assert json.loads(first.read_text()) == {"a": 1}


def test_failed_variant_does_not_emit_success(q_app, tmp_path):
    from unittest.mock import MagicMock

    from middleware.src.constants.comfy import ServerState

    manager, controller = MagicMock(), MagicMock()
    manager.queue_workflow.return_value = "failed-pid"
    manager.wait_for_run.return_value = False
    controller.server_state = ServerState.READY
    controller.run_http_action.side_effect = lambda action: action() or True
    widget = GuidanceDiffWidget(controller=controller, manager=manager, variant_dir=str(tmp_path))
    workflow, validation = _ok_validation()
    widget.set_guidance(workflow=workflow, validation=validation, source_prompt_id="p")
    successes = []
    widget.variant_queued.connect(successes.append)
    widget._on_requeue()
    assert not successes
    assert "did not complete" in widget._status.text()
    assert not widget._busy
    widget.deleteLater()


def test_checkbox_cannot_reenable_pending_submission(q_app):
    widget = GuidanceDiffWidget()
    workflow, validation = _ok_validation()
    widget.set_guidance(workflow=workflow, validation=validation)
    widget._busy = True
    widget.valid_toggles()[0].setChecked(False)
    widget.valid_toggles()[0].setChecked(True)
    assert not widget._requeue_btn.isEnabled()
    widget.deleteLater()
