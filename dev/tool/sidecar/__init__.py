"""Sidecar package: the bundled Python process the Tauri host spawns (#408).

The sidecar is the host's in-process Python surface: it can import this
monorepo's ``tool`` package and serve its evidence model, unlike a workspace
``command`` plugin (which must be spawned with a neutral interpreter). To keep
one process protocol on the host side, the sidecar speaks the *same* JSON-RPC
2.0-over-stdio contract as a command plugin (D52): initialize / list_artifacts
/ ping. The host spawns it as ``devtool sidecar --stdio``, appending ``--stdio``
exactly as it would for a command plugin.

Python is always bundled and isolated from the workspace (lock 5): the sidecar
never imports workspace packages and never uses ``./.venv`` or ``$PATH``
python on the consumer side. Its lifetime is the window (lock 3): spawned on
window open, killed on close. Restart policy lives in ``policy.py`` and encodes
locks 4 + 12.
"""

from .policy import MAX_AUTO_RESTARTS, RestartDecision, SidecarRestartPolicy
from .server import SidecarServer

__all__ = ["MAX_AUTO_RESTARTS", "RestartDecision", "SidecarRestartPolicy", "SidecarServer"]
