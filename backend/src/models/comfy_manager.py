import os
import sys
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

COMFYUI_DIR = Path(__file__).parents[3] / "ComfyUI"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8188


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
