"""tool: the modular Development Tool host + plugins (Track C).

    from tool import open_session, Host, WorkspaceStore
    session = open_session(pid=1234)

    python dev/                       # workspace chooser (no daemon)
    python dev/ plugins
    python dev/ list|analyze|tui|watch

``tool.debug`` keeps the original ``debugtool`` public surface for imports
(``tool.debug.open_session`` etc.) — folded in here 2026-08-17, no longer a
separate top-level package or CLI entry point. ``tool/devtool.py`` owns
``main()``; ``dev/__main__.py`` is what ``python dev/`` actually runs.
"""

from __future__ import annotations

from .export import export_session
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
from .host.git import git_state, write_session_manifest
from .host.scenarios import Scenario, get_scenario, list_scenarios
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
from .queries import (
    diff_sessions,
    format_diff,
    generate_hypothesis,
    rss_peak,
    rss_trajectory,
)
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
    "Scenario",
    "diff_sessions",
    "export_session",
    "format_diff",
    "generate_hypothesis",
    "get_scenario",
    "git_state",
    "list_scenarios",
    "write_session_manifest",
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
