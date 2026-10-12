"""Pre-flight workflow validation (#738): pure checks against a recorded
/object_info fixture pinned to the vendored vendor/ComfyUI revision, plus
the manager's cache lifecycle through a live HTTP stub.

No model, GPU, or ComfyUI process — the stub fixture is a threaded stdlib
HTTP server speaking the same JSON shapes as ComfyUI's /system_stats and
/object_info endpoints.
"""
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from backend.src.constants.comfy import ServerState
from backend.src.models.core.comfy_manager import ComfyUIManager
from backend.src.models.core.comfy_validation import (
    MISSING_FILE,
    MISSING_INPUT,
    MISSING_NODE,
    MODEL_FILE_FOLDERS,
    UNKNOWN_INPUT,
    validate_template,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "comfy_object_info.json"


@pytest.fixture(scope="module")
def object_info():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def endpoint(object_info):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = (object_info if self.path.startswith("/object_info")
                       else {"system": {}, "devices": []})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def _template():
    return ComfyUIManager.load_workflow("controlnet_generate.json")


def _populate_models_root(tmp_path, template):
    """Create the files a template references under a fake models dir."""
    for node in template.values():
        for name, value in (node.get("inputs") or {}).items():
            folders = MODEL_FILE_FOLDERS.get(name)
            if folders and isinstance(value, str):
                target = tmp_path / folders[0] / value
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x")
    return tmp_path


# ---------------------------------------------------------------------------
# Pure validation against the pinned recording
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["controlnet_generate.json", "ipadapter_generate.json"])
def test_shipped_templates_validate_clean_against_recording(object_info, tmp_path, name):
    template = ComfyUIManager.load_workflow(name)
    models_root = _populate_models_root(tmp_path, template)
    assert validate_template(template, object_info, models_root=models_root) == []


def test_unknown_node_type_is_reported(object_info, tmp_path):
    template = _template()
    template["5"]["class_type"] = "NotARealNode"
    issues = validate_template(template, object_info, models_root=tmp_path)
    assert [(i.node_id, i.code) for i in issues] == [("5", MISSING_NODE)]


def test_missing_required_input_is_reported(object_info, tmp_path):
    template = _template()
    del template["5"]["inputs"]["seed"]
    issues = validate_template(template, object_info, models_root=tmp_path)
    assert [(i.node_id, i.input_name, i.code) for i in issues] == [
        ("5", "seed", MISSING_INPUT)
    ]


def test_undeclared_input_is_reported(object_info, tmp_path):
    template = _template()
    template["5"]["inputs"]["bogus"] = 1
    issues = validate_template(template, object_info, models_root=tmp_path)
    assert [(i.node_id, i.input_name, i.code) for i in issues] == [
        ("5", "bogus", UNKNOWN_INPUT)
    ]


def test_missing_file_checked_against_server_choices(object_info, tmp_path):
    template = _template()
    template["8"]["inputs"]["control_net_name"] = "never_downloaded.pth"
    issues = validate_template(template, object_info, models_root=tmp_path)
    assert [(i.node_id, i.input_name, i.code) for i in issues] == [
        ("8", "control_net_name", MISSING_FILE)
    ]
    assert "never_downloaded.pth" in issues[0].message


def test_file_check_falls_back_to_local_models_root(object_info, tmp_path):
    """A node declaring a plain STRING widget (custom-node style) has no
    server choice list; the input name mapping drives the local check."""
    info = copy.deepcopy(object_info)
    info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = ["STRING", {}]
    template = _template()

    template["1"]["inputs"]["ckpt_name"] = "local_only.safetensors"
    assert validate_template(template, info, models_root=tmp_path) != []
    for folder in MODEL_FILE_FOLDERS["ckpt_name"]:
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    (tmp_path / "checkpoints" / "local_only.safetensors").write_text("x")
    assert validate_template(template, info, models_root=tmp_path) == []


def test_local_file_check_supports_nested_subfolders(object_info, tmp_path):
    info = copy.deepcopy(object_info)
    info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = ["STRING", {}]
    nested = tmp_path / "checkpoints" / "sdxl" / "animagine"
    nested.mkdir(parents=True)
    (nested / "xl.safetensors").write_text("x")
    template = _template()
    template["1"]["inputs"]["ckpt_name"] = "sdxl/animagine/xl.safetensors"
    assert validate_template(template, info, models_root=tmp_path) == []


def test_non_object_node_is_reported(object_info, tmp_path):
    template = _template()
    template["5"] = "garbage"
    issues = validate_template(template, object_info, models_root=tmp_path)
    assert ("5", MISSING_NODE) in [(i.node_id, i.code) for i in issues]


def test_validation_runs_without_object_info_when_models_root_given(tmp_path):
    template = _template()
    template["1"]["inputs"]["ckpt_name"] = "offline_check.safetensors"
    issues = validate_template(template, models_root=tmp_path)
    # No /object_info: every referenced model file is checked on local disk,
    # so the template's controlnet reference flags alongside our edited ckpt.
    assert [(i.code, i.input_name) for i in issues] == [
        (MISSING_FILE, "ckpt_name"),
        (MISSING_FILE, "control_net_name"),
    ]


# ---------------------------------------------------------------------------
# Manager cache lifecycle (live HTTP stub)
# ---------------------------------------------------------------------------


def test_validate_requires_cached_object_info():
    manager = ComfyUIManager()
    with pytest.raises(RuntimeError, match="Ready"):
        manager.validate_template(_template())


def test_object_info_warmed_at_ready_and_invalidated_on_leave(endpoint, tmp_path):
    manager = ComfyUIManager()
    received = threading.Event()
    captured = []
    manager.subscribe_object_info(lambda info: (captured.append(info), received.set()))

    assert manager.connect(endpoint.server_port)
    assert manager.state == ServerState.READY
    assert received.wait(timeout=5)
    assert captured[0] is not None
    assert manager.get_object_info() is not None

    template = _template()
    models_root = _populate_models_root(tmp_path, template)
    assert manager.validate_template(template, models_root=models_root) == []

    manager.stop()
    assert manager.state == ServerState.STOPPED
    assert manager.get_object_info() is None
    with pytest.raises(RuntimeError, match="Ready"):
        manager.validate_template(template)


def test_object_info_listener_gets_none_when_fetch_fails(monkeypatch):
    manager = ComfyUIManager()
    received = threading.Event()
    captured = []
    manager.subscribe_object_info(lambda info: (captured.append(info), received.set()))
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
    )
    manager._set_state(ServerState.READY)
    assert received.wait(timeout=10)
    assert captured[0] is None
    assert manager.get_object_info() is None
    manager._set_state(ServerState.STOPPED)


def test_warmup_race_with_state_change(endpoint, monkeypatch):
    """Leaving Ready while the fetch is in flight must not store a stale cache."""
    manager = ComfyUIManager()

    original = manager._get_json

    def slow_get_json(path, timeout=5.0):
        if path == "/object_info":
            event.wait(5)
        return original(path, timeout=timeout)

    event = threading.Event()
    monkeypatch.setattr(manager, "_get_json", slow_get_json)
    manager._set_state(ServerState.READY)
    event.set()
    manager._set_state(ServerState.STOPPED)
    assert manager.get_object_info() is None


def test_malformed_inputs_are_reported(object_info):
    graph = {"1": {"class_type": "KSampler", "inputs": ["bad"]}}
    issues = validate_template(graph, object_info)
    assert len(issues) == 1
    assert "must be an object" in issues[0].message


def test_reconnect_starts_new_warmup_while_old_request_is_blocked():
    manager = ComfyUIManager()
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def get_json(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
            return {"old": {}}
        return {"new": {}}

    manager._get_json = get_json
    manager._start_object_info_warmup()
    old = manager._object_info_thread
    try:
        assert entered.wait(1)
        manager._clear_object_info()
        manager._start_object_info_warmup()
        manager._object_info_thread.join(1)
        assert manager.get_object_info() == {"new": {}}
    finally:
        release.set()
        old.join(1)
        manager._clear_object_info()
