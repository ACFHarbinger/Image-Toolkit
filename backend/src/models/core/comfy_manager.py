import contextlib
import copy
import json
import mimetypes
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path

from backend.src.constants.comfy import ServerState
from backend.src.constants.models import DEFAULT_HOST, DEFAULT_PORT
from backend.src.models.core.comfy_provenance import ComfyRunRecord, RunTracker
from backend.src.models.core.comfy_validation import (
    TemplateIssue,
)
from backend.src.models.core.comfy_validation import (
    validate_template as _validate_template,
)

COMFYUI_DIR = Path(__file__).parents[4] / "vendor" / "ComfyUI"

# Curated ComfyUI workflow JSON templates (Content Gen §1.4, issue #35).
# Each file is a plain ComfyUI "API format" prompt graph (node id ->
# {inputs, class_type}) -- the same format ComfyUI's own "Save (API Format)"
# menu option produces, and the same format already used by the personal
# reference pipeline at configs/workflow_api.json.
WORKFLOWS_DIR = Path(__file__).parents[4] / "configs" / "comfy_workflows"

# /history window per poll; matches the tracker's baseline record limit.
HISTORY_POLL_ITEMS = 64
PROVENANCE_POLL_INTERVAL = 2.0


class ComfyUIManager:
    """Singleton that owns the ComfyUI server subprocess."""

    _instance: "ComfyUIManager | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._port: int = DEFAULT_PORT
        self._host: str = DEFAULT_HOST
        self._state = ServerState.STOPPED
        self._attached = False
        self._logs: queue.Queue[str] = queue.Queue(maxsize=1024)
        self._state_listeners: list[Callable[[ServerState], None]] = []
        self._log_listeners: list[Callable[[str], None]] = []
        # Run-provenance capture (#737): pure tracker + poller thread that
        # is driven by server state, never by any view.
        self._runs = RunTracker()
        self._provenance_lock = threading.Lock()
        self._poller_lock = threading.Lock()
        self._poll_interval = PROVENANCE_POLL_INTERVAL
        self._poll_stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        # Pre-flight validation (#738): /object_info fetched off-thread at
        # Ready, cached until the server leaves Ready.
        self._object_info: dict | None = None
        self._object_info_lock = threading.Lock()
        self._object_info_listeners: list[Callable[[dict | None], None]] = []
        self._object_info_thread: threading.Thread | None = None
        self._object_info_stop = threading.Event()

    @property
    def state(self) -> ServerState:
        return self._state

    @property
    def owns_server(self) -> bool:
        return self._process is not None

    def subscribe_state(self, listener: Callable[[ServerState], None]) -> None:
        self._state_listeners.append(listener)

    def subscribe_log(self, listener: Callable[[str], None]) -> None:
        self._log_listeners.append(listener)

    def subscribe_runs(self, listener: Callable[[ComfyRunRecord], None]) -> None:
        """Get every run-record create/update. Called on a worker thread;
        GUI consumers must marshal (queued signal or equivalent)."""
        self._runs.subscribe(listener)

    def get_run(self, prompt_id: str) -> ComfyRunRecord | None:
        with self._provenance_lock:
            return self._runs.get(prompt_id)

    def runs(self) -> tuple[ComfyRunRecord, ...]:
        with self._provenance_lock:
            return self._runs.snapshot()

    def _set_state(self, state: ServerState) -> None:
        if state == self._state:
            return
        self._state = state
        if state == ServerState.READY:
            self._start_provenance_poller()
            self._start_object_info_warmup()
        else:
            self._stop_provenance_poller()
            self._clear_object_info()
        for listener in tuple(self._state_listeners):
            listener(state)

    def connect(self, port: int = DEFAULT_PORT) -> bool:
        """Attach to a loopback server without acquiring process ownership."""
        if self.owns_server:
            raise RuntimeError("Stop the app-owned server before connecting to another server.")
        if not 1 <= port <= 65535:
            raise ValueError("Invalid ComfyUI port")
        self._port = port
        self._attached = True
        self._set_state(ServerState.STARTING)
        return self.refresh_state()

    def refresh_state(self, *, publish: bool = True) -> bool:
        if not self._attached and not self.is_running:
            if self._state != ServerState.STOPPED:
                self._set_state(ServerState.DISCONNECTED)
            return False
        try:
            with urllib.request.urlopen(f"{self.url}/system_stats", timeout=1) as response:
                stats = json.loads(response.read(1024 * 1024))
            ready = isinstance(stats, dict) and "system" in stats and "devices" in stats
        except (OSError, ValueError):
            ready = False
        if publish:
            self._set_state(ServerState.READY if ready else ServerState.DISCONNECTED)
        return ready

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "ComfyUIManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def port(self) -> int:
        return self._port

    # ------------------------------------------------------------------
    # Port helpers
    # ------------------------------------------------------------------

    def _port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((self._host, port)) == 0

    def _find_free_port(self, start: int) -> int:
        for port in range(start, start + 100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self._host, port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("Could not find a free port for ComfyUI in range "
                           f"{start}–{start + 99}.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, port: int = DEFAULT_PORT, enable_manager: bool = False) -> int:
        """Start the ComfyUI server and return the port it is listening on."""
        if getattr(sys, "frozen", False) and not COMFYUI_DIR.is_dir():
            raise RuntimeError(
                "ComfyUI server launch needs a source checkout with ComfyUI "
                f"at {COMFYUI_DIR}; not available in the packaged build. "
                "Connect to an already-running ComfyUI server instead."
            )

        if not 1 <= port <= 65535:
            raise ValueError("Invalid ComfyUI port")
        if self.is_running:
            return self._port
        if self._attached:
            raise RuntimeError("Disconnect the external server before starting a managed server.")

        if self._port_in_use(port):
            port = self._find_free_port(port + 1)

        self._port = port

        cmd = [
            sys.executable,
            str(COMFYUI_DIR / "main.py"),
            "--listen", self._host,
            "--port", str(self._port),
        ]

        if enable_manager:
            cmd.append("--enable-manager")

        self._set_state(ServerState.STARTING)
        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(COMFYUI_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ,
                     "HF_HUB_DISABLE_TELEMETRY": "1",
                     "DO_NOT_TRACK": "1"},
            )
        except Exception:
            self._set_state(ServerState.DISCONNECTED)
            raise
        process = self._process

        def drain() -> None:
            if process.stdout is not None:
                for line in process.stdout:
                    with contextlib.suppress(queue.Full):
                        self._logs.put_nowait(line)
                    for listener in tuple(self._log_listeners):
                        listener(line)

        threading.Thread(target=drain, daemon=True, name="comfy-server-log").start()
        return self._port

    def stop(self) -> None:
        """Terminate the ComfyUI server process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._process = None
        self._attached = False
        self._set_state(ServerState.STOPPED)

    # ------------------------------------------------------------------
    # Readiness / log streaming
    # ------------------------------------------------------------------

    def wait_until_ready(
        self, timeout: float = 90.0, cancel: threading.Event | None = None,
    ) -> bool:
        """Probe off the GUI thread; cancellation never terminates an external server."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancel is not None and cancel.is_set():
                return False
            if not self.is_running and not self._attached:
                self._set_state(ServerState.DISCONNECTED)
                return False
            if self.refresh_state(publish=False):
                self._set_state(ServerState.READY)
                return True
            if cancel is not None:
                if cancel.wait(0.5):
                    return False
            else:
                time.sleep(0.5)
        self._set_state(ServerState.DISCONNECTED)
        return False

    def iter_log_lines(self):
        """Yield lines from the server's stdout (blocks per line)."""
        while self.is_running or not self._logs.empty():
            try:
                yield self._logs.get(timeout=0.25)
            except queue.Empty:
                continue

    # ------------------------------------------------------------------
    # Run provenance (#737)
    #
    # /queue + /history are polled whenever the server is Ready so the
    # executed API-format graph, inputs, and outputs are captured as run
    # records regardless of how the user drove the server (app queue call
    # or their own browser). Capture stops with the poller on any state
    # change away from Ready; records already captured stay queryable.
    # ------------------------------------------------------------------

    def _get_json(self, path: str, timeout: float = 5.0) -> dict:
        with urllib.request.urlopen(f"{self.url}{path}", timeout=timeout) as response:
            return json.loads(response.read(8 * 1024 * 1024))

    def _start_provenance_poller(self) -> None:
        with self._poller_lock:
            if self._poll_thread is not None and self._poll_thread.is_alive():
                return
            # Each poller gets its own stop event so a restart can never
            # resurrect a poller that is still winding down.
            stop = threading.Event()
            self._poll_stop = stop
            self._poll_thread = threading.Thread(
                target=self._poll_provenance,
                args=(stop,),
                daemon=True,
                name="comfy-provenance",
            )
            self._poll_thread.start()

    def _stop_provenance_poller(self) -> None:
        with self._poller_lock:
            thread = self._poll_thread
            self._poll_thread = None
            self._poll_stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.5)

    def _poll_provenance(self, stop: threading.Event) -> None:
        first = True
        while not stop.wait(self._poll_interval):
            try:
                queue_info = self._get_json("/queue")
                history = self._get_json(f"/history?max_items={HISTORY_POLL_ITEMS}")
            except (OSError, ValueError):
                # Transient failures retry on the next tick; state changes
                # away from Ready stop this thread via the event.
                continue
            with self._provenance_lock:
                self._runs.observe_snapshot(queue_info, history, first=first)
            first = False

    # ------------------------------------------------------------------
    # Pre-flight validation (#738)
    #
    # /object_info is the expensive half of template validation, so it is
    # fetched once per Ready transition on a worker thread and cached until
    # the server leaves Ready. validate_template() itself is pure CPU + a
    # local models-dir listing, safe to call from the GUI thread.
    # ------------------------------------------------------------------

    def subscribe_object_info(self, listener: Callable[[dict | None], None]) -> None:
        """Get the cached /object_info once fetched at Ready. Called on a
        worker thread; a None argument means the fetch failed (fail open)."""
        self._object_info_listeners.append(listener)

    def get_object_info(self) -> dict | None:
        with self._object_info_lock:
            return self._object_info

    def validate_template(
        self,
        template: dict,
        *,
        object_info: dict | None = None,
        models_root: Path | None = None,
    ) -> list[TemplateIssue]:
        """Check one API-format workflow graph before it is queued.

        Node types/inputs are checked against /object_info (cached at Ready;
        pass *object_info* to validate against a recording instead, e.g. the
        pinned fixture in backend/test/fixtures). Referenced model files are
        checked under *models_root* (default COMFYUI_DIR/models) when the
        node's /object_info spec declares no choice list for the input.
        """
        if object_info is None:
            object_info = self.get_object_info()
        if object_info is None:
            raise RuntimeError(
                "No /object_info available — validate once the server is Ready."
            )
        if models_root is None:
            models_root = COMFYUI_DIR / "models"
        return _validate_template(template, object_info, models_root=models_root)

    def _start_object_info_warmup(self) -> None:
        with self._object_info_lock:
            if (self._object_info_thread is not None
                    and self._object_info_thread.is_alive()):
                return
            # Each warmup gets its own stop event so a restart can never
            # resurrect one that is still winding down.
            stop = threading.Event()
            self._object_info_stop = stop
            self._object_info_thread = threading.Thread(
                target=self._fetch_object_info,
                args=(stop,),
                daemon=True,
                name="comfy-object-info",
            )
            self._object_info_thread.start()

    def _clear_object_info(self) -> None:
        self._object_info_stop.set()
        thread = self._object_info_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        with self._object_info_lock:
            self._object_info = None

    def _fetch_object_info(self, stop: threading.Event) -> None:
        info: dict | None = None
        for attempt in range(3):
            if stop.is_set():
                return
            try:
                info = self._get_json("/object_info", timeout=10)
                break
            except (OSError, ValueError):
                if stop.wait(1.0 * (attempt + 1)):
                    return
        # Re-check under the lock: a state change away from Ready may have
        # landed while the fetch was in flight.
        with self._object_info_lock:
            if stop.is_set():
                return
            self._object_info = info
        for listener in tuple(self._object_info_listeners):
            listener(info)

    # ------------------------------------------------------------------
    # Workflow JSON launch path (Content Gen §1.4 / issue #35)
    #
    # The pre-existing manager only started/stopped the ComfyUI server and
    # let the user drive its own web UI by hand -- there was no mechanism
    # in this codebase to submit a curated workflow JSON with parameter
    # overrides via ComfyUI's HTTP API. Rather than a larger refactor, this
    # adds the smallest correct extension: load a workflow template, apply
    # a generic {node_id: {input_key: value}} override dict to it (used for
    # things like swapping in a ControlNet control image or an IP-Adapter
    # reference image), upload any extra input image ComfyUI needs to see
    # on disk, and queue the resulting prompt graph.
    # ------------------------------------------------------------------

    @staticmethod
    def load_workflow(name_or_path: str) -> dict:
        """Load a curated workflow JSON template.

        *name_or_path* may be a bare filename looked up under
        ``configs/comfy_workflows/`` (e.g. ``"controlnet_generate.json"``)
        or an absolute/relative path to any workflow JSON file.
        """
        path = Path(name_or_path)
        if not path.is_absolute() and not path.exists():
            path = WORKFLOWS_DIR / path.name
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def apply_overrides(workflow: dict, overrides: dict[str, dict]) -> dict:
        """Return a copy of *workflow* with per-node input overrides applied.

        *overrides* maps node id (string, matching the workflow JSON's own
        keys) to a dict of ``{input_name: value}`` to merge into that
        node's ``"inputs"``. Unknown node ids are ignored rather than
        raising, so the same override dict can be reused across workflow
        templates that don't all define every node.
        """
        result = copy.deepcopy(workflow)
        for node_id, node_overrides in (overrides or {}).items():
            node = result.get(node_id)
            if node is None:
                continue
            node.setdefault("inputs", {}).update(node_overrides)
        return result

    def upload_image(self, image_path: str) -> str:
        """Upload a local image to the running ComfyUI server's input
        folder and return the server-side filename to reference from a
        ``LoadImage`` node's ``image`` input (e.g. a ControlNet control
        image or an IP-Adapter reference image).
        """
        src = Path(image_path)
        boundary = uuid.uuid4().hex
        content_type = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
        data = src.read_bytes()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{src.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            f"{self.url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("name", src.name)

    def queue_workflow(self, workflow: dict, client_id: str | None = None) -> str:
        """Submit a workflow (API-format prompt graph) to the running
        ComfyUI server's ``/prompt`` endpoint. Returns the server's
        ``prompt_id``.
        """
        payload = {"prompt": workflow}
        if client_id:
            payload["client_id"] = client_id
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ComfyUI rejected the workflow: {detail}") from exc
        prompt_id = result["prompt_id"]
        with self._provenance_lock:
            self._runs.record_submitted(prompt_id, workflow, client_id)
        return prompt_id
