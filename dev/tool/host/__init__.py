"""tool host: process lifecycle, plugin protocol, settings, store.

Deepseek's slice (data side): plugins.py (protocol), settings.py (policy),
store.py (workspace persistence + plugin loading). Grok's slice (lifecycle +
discovery) lands in app.py next.
"""

from __future__ import annotations

from .app import Host, RegisteredView, discover_plugins
from .index import INDEX_FILENAME, build_index, index_path, write_index
from .plugins import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA,
    MANIFEST_SCHEMA_VERSION,
    Artifact,
    Channel,
    Plugin,
    PluginEntry,
    PluginManifest,
    Surface,
    build_command_argv,
    load_manifest,
    write_manifest,
)
from .settings import SETTINGS_FILENAME, Settings
from .store import WorkspaceStore, default_workspace_root

__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA",
    "MANIFEST_SCHEMA_VERSION",
    "Artifact",
    "Channel",
    "Host",
    "INDEX_FILENAME",
    "Plugin",
    "PluginEntry",
    "PluginManifest",
    "RegisteredView",
    "SETTINGS_FILENAME",
    "Settings",
    "Surface",
    "WorkspaceStore",
    "build_command_argv",
    "build_index",
    "default_workspace_root",
    "discover_plugins",
    "index_path",
    "load_manifest",
    "write_index",
    "write_manifest",
]
