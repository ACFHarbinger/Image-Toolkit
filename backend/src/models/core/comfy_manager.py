import copy
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

COMFYUI_DIR = Path(__file__).parents[3] / "ComfyUI"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8188

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
        if self.is_running:
            return self._port

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

    # ------------------------------------------------------------------
    # Readiness / log streaming
    # ------------------------------------------------------------------

    def wait_until_ready(self, timeout: float = 90.0) -> bool:
        """Block until the HTTP server responds or *timeout* seconds elapse."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_running:
                return False
            try:
                urllib.request.urlopen(self.url, timeout=1)
                return True
            except Exception:
                time.sleep(0.5)
        return False

    def iter_log_lines(self):
        """Yield lines from the server's stdout (blocks per line)."""
        if self._process and self._process.stdout:
            yield from self._process.stdout

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
