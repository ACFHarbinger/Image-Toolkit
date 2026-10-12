"""Run-provenance capture (#737): pure tracker logic plus live HTTP-stub polling.

No model, GPU, or ComfyUI process is involved — the stub fixture is a
threaded stdlib HTTP server speaking the same JSON shapes as ComfyUI's
/queue, /history and /prompt endpoints (verified against the vendored
vendor/ComfyUI/server.py and execution.py).
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.src.constants.comfy import RunStatus, ServerState
from backend.src.models.core.comfy_manager import ComfyUIManager
from backend.src.models.core.comfy_provenance import (
    BASELINE_RECORD_LIMIT,
    ComfyRunRecord,
    OutputRef,
    RunTracker,
)


def queue_item(number: int, prompt_id: str, graph=None):
    return [number, prompt_id, graph if graph is not None else {"nodes": number}, {}, ["9"]]


def history_entry(number: int, prompt_id: str, *, status=None, outputs=None, graph=None):
    return {
        "prompt": queue_item(number, prompt_id, graph),
        "outputs": outputs or {},
        "status": status,
    }


def success_status():
    return {"status_str": "success", "completed": True, "messages": []}


def image_output(filename):
    return {"9": {"images": [{"filename": filename}]}}


# ---------------------------------------------------------------------------
# Pure tracker
# ---------------------------------------------------------------------------


def test_surface_metadata_survives_history_and_exposes_output_paths():
    tracker = RunTracker()
    overrides = {"5": {"seed": 1}}
    tracker.record_submitted(
        "p-meta",
        {"1": {"inputs": {"seed": 1}}},
        client_id="app",
        run_meta={
            "surface_mode": "guided",
            "template_name": "controlnet_generate.json",
            "applied_overrides": overrides,
            "sweep_axis": None,
        },
    )
    overrides["5"]["seed"] = 99
    assert tracker.get("p-meta").applied_overrides["5"]["seed"] == 1
    tracker.observe_history(
        {
            "p-meta": history_entry(
                4,
                "p-meta",
                status=success_status(),
                outputs=image_output("out.png"),
                graph={"nodes": "server"},
            )
        }
    )
    record = tracker.get("p-meta")
    assert record.status is RunStatus.COMPLETED
    assert record.workflow == {"nodes": "server"}
    assert record.surface_mode == "guided"
    assert record.template_name == "controlnet_generate.json"
    assert record.applied_overrides == {"5": {"seed": 1}}
    assert record.output_paths == ("out.png",)


def test_submitted_record_lifecycle_through_queue_and_history():
    tracker = RunTracker()
    seen = []
    tracker.subscribe(seen.append)
    tracker.record_submitted("p1", {"graph": 1}, client_id="c1")
    assert tracker.get("p1").status is RunStatus.PENDING
    assert tracker.get("p1").source == "submitted"

    tracker.observe_queue({"queue_running": [queue_item(1, "p1")], "queue_pending": []})
    assert tracker.get("p1").status is RunStatus.RUNNING

    tracker.observe_history(
        {
            "p1": history_entry(
                1,
                "p1",
                status=success_status(),
                outputs=image_output("o.png"),
            )
        }
    )
    record = tracker.get("p1")
    assert record.status is RunStatus.COMPLETED
    # The executed graph (server echo) is the provenance truth, not the
    # optimistic submitted copy.
    assert record.workflow == {"nodes": 1}
    assert record.outputs == (OutputRef("9", "images", "o.png", "", "output"),)
    assert not record.partial
    assert [r.status for r in seen] == [
        RunStatus.PENDING,
        RunStatus.RUNNING,
        RunStatus.COMPLETED,
    ]


def test_baseline_emits_only_newest_window():
    tracker = RunTracker()
    emitted = []
    tracker.subscribe(emitted.append)
    history = {
        f"p{i}": history_entry(i, f"p{i}", status=success_status())
        for i in range(BASELINE_RECORD_LIMIT + 10)
    }
    tracker.observe_snapshot({}, history, first=True)
    assert len(emitted) == BASELINE_RECORD_LIMIT
    assert {r.prompt_id for r in emitted} == {
        f"p{i}" for i in range(10, 10 + BASELINE_RECORD_LIMIT)
    }
    # Older ids are marked seen: a later poll never re-emits them.
    tracker.observe_history(history)
    assert len(emitted) == BASELINE_RECORD_LIMIT


def test_error_and_interrupted_entries_map_to_terminal_status():
    tracker = RunTracker()
    history = {
        "err": history_entry(1, "err", status={"status_str": "error", "completed": True, "messages": []}),
        "int": history_entry(
            2,
            "int",
            status={"status_str": "error", "completed": True, "messages": [["execution_interrupted", {}]]},
        ),
    }
    tracker.observe_history(history)
    assert tracker.get("err").status is RunStatus.FAILED
    assert tracker.get("int").status is RunStatus.INTERRUPTED


def test_missing_status_or_graph_is_partial():
    tracker = RunTracker()
    tracker.observe_history({"old": {"outputs": {}}})
    record = tracker.get("old")
    assert record.status is RunStatus.COMPLETED
    assert record.partial
    assert record.workflow is None

    tracker2 = RunTracker()
    tracker2.observe_history(
        {"no": history_entry(1, "no", status=success_status(), graph="not-a-dict")}
    )
    assert tracker2.get("no").partial


def test_cancelled_queue_item_is_interrupted_after_grace():
    tracker = RunTracker()
    tracker.observe_queue({"queue_running": [], "queue_pending": [queue_item(1, "p1")]})
    assert tracker.get("p1").status is RunStatus.PENDING
    tracker.observe_queue({"queue_running": [], "queue_pending": []})
    assert tracker.get("p1").status is RunStatus.PENDING
    tracker.observe_queue({"queue_running": [], "queue_pending": []})
    record = tracker.get("p1")
    assert record.status is RunStatus.INTERRUPTED
    assert record.partial


def test_records_are_bounded_and_snapshot_is_ordered():
    tracker = RunTracker(record_limit=3)
    for i in range(8):
        tracker.record_submitted(f"p{i}", {"i": i}, None)
    assert [r.prompt_id for r in tracker.snapshot()] == ["p5", "p6", "p7"]
    assert tracker.get("p0") is None


def test_unknown_history_id_is_captured_as_completed():
    """Work the user did in an external browser while the app was away."""
    tracker = RunTracker()
    tracker.observe_snapshot(
        {},
        {"theirs": history_entry(1, "theirs", status=success_status(), outputs=image_output("x.png"))},
        first=False,
    )
    record = tracker.get("theirs")
    assert record.status is RunStatus.COMPLETED
    assert record.outputs == (OutputRef("9", "images", "x.png", "", "output"),)
    assert record.source == "history"


def test_terminal_records_are_not_resurrected_by_queue_noise():
    tracker = RunTracker()
    tracker.observe_history({"p1": history_entry(1, "p1", status=success_status())})
    assert tracker.get("p1").status is RunStatus.COMPLETED
    tracker.observe_queue({"queue_running": [queue_item(1, "p1")], "queue_pending": []})
    assert tracker.get("p1").status is RunStatus.COMPLETED


def test_output_ref_view_url_quotes_components():
    ref = OutputRef("9", "images", "a b.png", "sub dir", "output")
    assert ref.view_url("http://127.0.0.1:8188") == (
        "http://127.0.0.1:8188/view?filename=a%20b.png&subfolder=sub%20dir&type=output"
    )


def test_record_is_immutable_dataclass():
    from dataclasses import FrozenInstanceError

    record = ComfyRunRecord(prompt_id="p", status=RunStatus.PENDING)
    with pytest.raises(FrozenInstanceError):
        record.status = RunStatus.RUNNING  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Manager polling against a live HTTP stub
# ---------------------------------------------------------------------------


class StubState:
    """Shared, lock-guarded view of what the fake server reports."""

    def __init__(self):
        self.lock = threading.Lock()
        self.queue = {"queue_running": [], "queue_pending": []}
        self.history = {}
        self.history_hits = 0
        self.dark = False

    def put(self, item):
        with self.lock:
            self.queue["queue_pending"].append(item)

    def finish(self, prompt_id, entry):
        with self.lock:
            for group in ("queue_running", "queue_pending"):
                self.queue[group] = [i for i in self.queue[group] if i[1] != prompt_id]
            self.history[prompt_id] = entry


class _QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


@pytest.fixture
def stub():
    state = StubState()

    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if state.dark:
                # Drop the connection without a response: the client sees
                # RemoteDisconnected (an OSError), like a dead server.
                self.connection.close()
                return
            path = self.path.split("?")[0]
            with state.lock:
                if path == "/system_stats":
                    self._json({"system": {}, "devices": []})
                elif path == "/queue":
                    self._json(state.queue)
                elif path == "/history":
                    state.history_hits += 1
                    self._json(state.history)
                else:
                    self.send_response(404)
                    self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self._json({"prompt_id": "local-1"})

        def log_message(self, *args):
            pass

    server = _QuietServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state, server.server_port
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def manager(stub):
    _state, _port = stub
    manager = ComfyUIManager()
    manager._poll_interval = 0.05
    yield manager
    manager.stop()


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_poller_captures_queue_run_to_completion(stub, manager):
    state, port = stub
    state.put(queue_item(1, "live-1"))
    records = []
    manager.subscribe_runs(records.append)
    assert manager.connect(port)
    assert manager.state == ServerState.READY

    assert wait_for(lambda: manager.get_run("live-1") is not None)
    assert manager.get_run("live-1").status in (RunStatus.PENDING, RunStatus.RUNNING)
    assert manager.get_run("live-1").workflow == {"nodes": 1}

    state.finish("live-1", history_entry(1, "live-1", status=success_status(), outputs=image_output("live.png")))
    assert wait_for(lambda: manager.get_run("live-1").status is RunStatus.COMPLETED)
    record = manager.get_run("live-1")
    assert record.outputs == (OutputRef("9", "images", "live.png", "", "output"),)
    assert any(r.status is RunStatus.COMPLETED for r in records)


def test_poller_stops_on_stop_and_records_survive(stub, manager):
    state, port = stub
    state.put(queue_item(2, "gone-1"))
    assert manager.connect(port)
    assert wait_for(lambda: manager.get_run("gone-1") is not None)
    manager.stop()
    assert manager.state == ServerState.STOPPED
    assert manager._poll_thread is None
    hits_after_stop = state.history_hits
    time.sleep(0.3)
    assert state.history_hits == hits_after_stop
    assert manager.get_run("gone-1") is not None


def test_queue_workflow_creates_optimistic_record(stub, manager):
    _state, port = stub
    assert manager.connect(port)
    prompt_id = manager.queue_workflow({"k": {"class_type": "X", "inputs": {}}}, client_id="app")
    assert prompt_id == "local-1"
    record = manager.get_run(prompt_id)
    assert record.status is RunStatus.PENDING
    assert record.workflow == {"k": {"class_type": "X", "inputs": {}}}
    assert record.client_id == "app"
    assert record.source == "submitted"


def test_baseline_on_first_poll_is_windowed(stub, manager):
    state, port = stub
    with state.lock:
        for i in range(BASELINE_RECORD_LIMIT + 4):
            state.history[f"old-{i}"] = history_entry(i, f"old-{i}", status=success_status())
    assert manager.connect(port)
    assert wait_for(lambda: len(manager.runs()) == BASELINE_RECORD_LIMIT)
    assert all(r.prompt_id.startswith("old-") for r in manager.runs())
    assert {r.status for r in manager.runs()} == {RunStatus.COMPLETED}


def test_disconnect_stops_capture_and_reconnect_resumes_it(stub, manager):
    state, port = stub
    state.put(queue_item(3, "net-1"))
    assert manager.connect(port)
    assert wait_for(lambda: manager.get_run("net-1") is not None)

    state.dark = True
    assert not manager.refresh_state(publish=True)
    assert manager.state == ServerState.DISCONNECTED
    assert manager._poll_thread is None
    kept = manager.runs()
    assert any(r.prompt_id == "net-1" for r in kept)

    state.dark = False
    assert manager.refresh_state(publish=True)
    assert manager.state == ServerState.READY
    state.finish("net-1", history_entry(3, "net-1", status=success_status(), outputs=image_output("net.png")))
    assert wait_for(lambda: manager.get_run("net-1").status is RunStatus.COMPLETED)
    assert len([r for r in manager.runs() if r.prompt_id == "net-1"]) == 1
    # Everything captured before the blip is still there exactly once.
    assert len(manager.runs()) == len(kept)


def test_late_history_corrects_inferred_interruption():
    tracker = RunTracker()
    tracker.record_submitted("late", {"optimistic": 1}, None)
    tracker.observe_snapshot({}, {}, first=False)
    tracker.observe_snapshot({}, {}, first=False)
    assert tracker.get("late").status is RunStatus.INTERRUPTED
    tracker.observe_snapshot({}, {"late": history_entry(
        1, "late", status=success_status(), graph={"executed": 2},
        outputs=image_output("result.png"),
    )}, first=False)
    record = tracker.get("late")
    assert record.status is RunStatus.COMPLETED
    assert record.workflow == {"executed": 2}
    assert record.output_paths == ("result.png",)
    assert not record.partial
    tracker.record_submitted("late", {"optimistic": 1}, None,
                             run_meta={"surface_mode": "guided"})
    assert tracker.get("late").workflow == {"executed": 2}
    assert tracker.get("late").surface_mode == "guided"


def test_vanishing_requires_consecutive_absences():
    tracker = RunTracker()
    tracker.record_submitted("p", {}, None)
    tracker.observe_queue({})
    tracker.observe_queue({"queue_running": [queue_item(1, "p")]})
    tracker.observe_queue({})
    assert tracker.get("p").status is RunStatus.RUNNING


def test_provenance_does_not_share_mutable_graphs():
    graph = {"1": {"inputs": {"seed": 1}}}
    tracker = RunTracker()
    tracker.record_submitted("p", graph, None)
    graph["1"]["inputs"]["seed"] = 2
    record = tracker.get("p")
    assert record.workflow["1"]["inputs"]["seed"] == 1
    record.workflow.clear()
    assert tracker.get("p").workflow


def test_wait_for_run_waits_for_history_after_queue_ack():
    manager = ComfyUIManager()
    manager._state = ServerState.READY
    terminal = {"p": history_entry(1, "p", status=success_status())}
    responses = iter([{}, {"queue_running": [queue_item(1, "p")]}, terminal])
    paths = []

    def get_json(path):
        paths.append(path)
        return next(responses)

    manager._get_json = get_json
    assert manager.wait_for_run("p")
    assert paths == ["/history/p", "/queue", "/history/p"]


def test_wait_for_run_stops_when_pending_prompt_is_deleted():
    manager = ComfyUIManager()
    manager._state = ServerState.READY
    manager._get_json = lambda _path: {}
    assert manager.wait_for_run("deleted") is False
    cancel = threading.Event()
    cancel.set()
    assert manager.wait_for_run("cancelled", cancel=cancel) is False


def test_variant_label_meta_passthrough():
    """#752: re-queued runs carry a render-only origin label plus the parent link."""
    tracker = RunTracker()
    tracker.record_submitted(
        "p-var",
        {"1": {"inputs": {}}},
        client_id="c",
        run_meta={"parent_prompt_id": "p-orig", "variant_label": "assistant-suggested"},
    )
    record = tracker.get("p-var")
    assert record.parent_prompt_id == "p-orig"
    assert record.variant_label == "assistant-suggested"


def test_variant_label_defaults_to_none():
    tracker = RunTracker()
    tracker.record_submitted("p-plain", {"1": {}}, client_id="c")
    assert tracker.get("p-plain").variant_label is None
