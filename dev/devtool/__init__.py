"""devtool: the modular Development Tool host + plugins (Track C).

Public data-side API (deepseek's slice; process lifecycle + discovery is
Grok's and lands in host/app.py next):

    from devtool import WorkspaceStore, Investigation, Session
    store = WorkspaceStore(root=...)
    plugin = store.load_plugin("devtool.plugins.telemetry_workbench:plugin")
    store.list_artifacts(plugin)      # sessions + investigations

The working telemetry package remains debug/debugtool until C2 lands the
devtool alias; this package imports its Session model from there.
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
    Plugin,
    PluginManifest,
    Settings,
    Surface,
    WorkspaceStore,
    default_workspace_root,
)

__all__ = [
    "TELEMETRY_DIR",
    "Artifact",
    "Channel",
    "CrashBundle",
    "Event",
    "Investigation",
    "Plugin",
    "PluginManifest",
    "ProcessTree",
    "Session",
    "Settings",
    "Span",
    "Surface",
    "WorkspaceStore",
    "default_workspace_root",
    "discover_sessions",
    "session_path_for_pid",
]
