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
from .workspace import (
    DEFAULT_MONITOR_DEPTH,
    PluginSource,
    STATE_FILENAME,
    WORKSPACE_CONFIG_FILENAME,
    WorkspaceConfig,
    config_dir,
    discover_plugin_sources,
    global_plugins_dir,
    load_last_workspace,
    load_workspace_config,
    save_last_workspace,
    state_path,
)

__all__ = [
    "DEFAULT_MONITOR_DEPTH",
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
    "PluginSource",
    "RegisteredView",
    "SETTINGS_FILENAME",
    "STATE_FILENAME",
    "Settings",
    "Surface",
    "WORKSPACE_CONFIG_FILENAME",
    "WorkspaceConfig",
    "WorkspaceStore",
    "build_command_argv",
    "build_index",
    "config_dir",
    "default_workspace_root",
    "discover_plugin_sources",
    "discover_plugins",
    "global_plugins_dir",
    "index_path",
    "load_last_workspace",
    "load_manifest",
    "load_workspace_config",
    "save_last_workspace",
    "state_path",
    "write_index",
    "write_manifest",
]
