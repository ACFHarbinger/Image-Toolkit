"""devtool host: process lifecycle, plugin protocol, settings, store.

Deepseek's slice (data side): plugins.py (protocol), settings.py (policy),
store.py (workspace persistence + plugin loading). Grok's slice (lifecycle +
discovery) lands in app.py next.
"""

from __future__ import annotations

from .plugins import (
    Artifact,
    Channel,
    Plugin,
    PluginManifest,
    Surface,
)
from .settings import SETTINGS_FILENAME, Settings
from .store import WorkspaceStore, default_workspace_root

__all__ = [
    "Artifact",
    "Channel",
    "Plugin",
    "PluginManifest",
    "SETTINGS_FILENAME",
    "Settings",
    "Surface",
    "WorkspaceStore",
    "default_workspace_root",
]
