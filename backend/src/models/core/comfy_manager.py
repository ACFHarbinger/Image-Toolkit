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

COMFYUI_DIR = Path(__file__).parents[4] / "vendor" / "ComfyUI"

# Curated ComfyUI workflow JSON templates (Content Gen §1.4, issue #35).
# Each file is a plain ComfyUI "API format" prompt graph (node id ->
# {inputs, class_type}) -- the same format ComfyUI's own "Save (API Format)"
# menu option produces, and the same format already used by the personal
# reference pipeline at configs/workflow_api.json.
WORKFLOWS_DIR = Path(__file__).parents[4] / "configs" / "comfy_workflows"


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

    def _set_state(self, state: ServerState) -> None:
        if state == self._state:
            return
        self._state = state
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
        return result["prompt_id"]
