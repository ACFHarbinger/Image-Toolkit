"""devtool: the modular Development Tool host + plugins (Track C).

    from devtool import Host, WorkspaceStore
    host = Host(store=WorkspaceStore(root=...))
    host.discover()                   # first-party plugins
    host.artifacts("telemetry_workbench")

    python -m devtool                 # workspace chooser (no daemon)
    python -m devtool plugins

Telemetry analysis stays in debug/debugtool until C2.
"""

from __future__ import annotations

from .model import (
    TELEMETRY_DIR,
    CrashBundle,
    Event,
    Investigation,
    ProcessTree,
    Session,
    Span,
    discover_sessions,
    session_path_for_pid,
)
from .host import (
    Artifact,
    Channel,
    Host,
    Plugin,
    PluginManifest,
    RegisteredView,
    Settings,
    Surface,
    WorkspaceStore,
    default_workspace_root,
    discover_plugins,
)

__all__ = [
    "TELEMETRY_DIR",
    "Artifact",
    "Channel",
    "CrashBundle",
    "Event",
    "Host",
    "Investigation",
    "Plugin",
    "PluginManifest",
    "ProcessTree",
    "RegisteredView",
    "Session",
    "Settings",
    "Span",
    "Surface",
    "WorkspaceStore",
    "default_workspace_root",
    "discover_plugins",
    "discover_sessions",
    "session_path_for_pid",
]
