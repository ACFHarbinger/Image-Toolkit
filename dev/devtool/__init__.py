"""devtool: the modular Development Tool host + plugins (Track C).

    from devtool import open_session, Host, WorkspaceStore
    session = open_session(pid=1234)

    python -m devtool                 # workspace chooser (no daemon)
    python -m devtool plugins
    python -m devtool list|analyze|tui|watch

``python -m debugtool`` is a permanent alias of this CLI (C2).
"""

from __future__ import annotations

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
from .export import export_session
from .mcp import McpServer
from .model import (
    TELEMETRY_DIR,
    CrashBundle,
    Event,
    Investigation,
    ProcessTree,
    Session,
    Span,
    discover_sessions,
    list_sessions,
    open_session,
    session_path_for_pid,
)
from .queries import diff_sessions, format_diff, rss_peak, rss_trajectory
from .ui.web import WebServer

__all__ = [
    "TELEMETRY_DIR",
    "Artifact",
    "Channel",
    "CrashBundle",
    "Event",
    "Host",
    "Investigation",
    "McpServer",
    "Plugin",
    "diff_sessions",
    "export_session",
    "format_diff",
    "PluginManifest",
    "ProcessTree",
    "RegisteredView",
    "Session",
    "Settings",
    "Span",
    "Surface",
    "WebServer",
    "WorkspaceStore",
    "rss_peak",
    "rss_trajectory",
    "default_workspace_root",
    "discover_plugins",
    "discover_sessions",
    "list_sessions",
    "open_session",
    "session_path_for_pid",
]
