"""Python sidecar for the Tauri bridge (W0-12, #876; Codex R1/R6).

Speaks the versioned JSON-RPC/stdio contract from ``contracts/`` via the
shared bridge package (W0-11, #875) — framing, envelope, handshake and
cancel semantics are never re-implemented here. stdout carries only framed
protocol messages; diagnostics go to stderr redacted (no tracebacks).

Launched as ``python -m middleware.src.sidecar [--data-dir DIR]`` — the
argv shape the W0-13 supervisor (#877) hands to ``children.spawn()``; with
``--data-dir`` the sidecar writes the ``sidecar.heartbeat`` file the
supervisor's readiness gate (``bridge.ready``) waits on.

Startup stays lightweight: no Torch/cv2 import until a service handler
lazy-imports it (real services land in later waves; ``jobs.*`` here is the
in-memory reference skeleton).
"""

from .jobs import JobRegistry
from .server import SidecarServer

__all__ = ["JobRegistry", "SidecarServer"]
