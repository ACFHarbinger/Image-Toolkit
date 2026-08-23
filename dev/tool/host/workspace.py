"""Workspace config (devtool.toml), plugin discovery, and last-workspace state (v2 #412).

D53/D60: a workspace monitors exactly one user-selected repository. Plugin
discovery is global (~/.config/devtool/plugins/*.plugin.json) plus
per-workspace (a devtool.toml at the repo root may declare additional
plugins); the host merges them, workspace overriding global by name.

Last-workspace restore (Grok lock #13): the selected workspace is persisted
in ~/.config/devtool/state.json and restored when no explicit --workspace is
given (one key back to the picker).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

WORKSPACE_CONFIG_FILENAME = "devtool.toml"
STATE_FILENAME = "state.json"
DEFAULT_MONITOR_DEPTH = 3


def config_dir() -> Path:
    return Path.home() / ".config" / "devtool"


def global_plugins_dir() -> Path:
    return config_dir() / "plugins"


def state_path() -> Path:
    return config_dir() / STATE_FILENAME


# ---------------------------------------------------------------------------
# Last-workspace state (lock #13)
# ---------------------------------------------------------------------------

def save_last_workspace(root: Path) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    state_path().write_text(
        json.dumps({"last_workspace": str(root)}, indent=2) + chr(10),
        encoding="utf-8",
    )


def load_last_workspace() -> Optional[Path]:
    path = state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    last = data.get("last_workspace")
    if not last:
        return None
    root = Path(last)
    return root if root.is_dir() else None


# ---------------------------------------------------------------------------
# devtool.toml workspace config
# ---------------------------------------------------------------------------

@dataclass
class PluginSource:
    """One workspace-declared plugin: a manifest path or an inline entry."""

    name: str
    manifest: Optional[Path] = None  # resolved relative to the workspace root
    python_module: str = ""
    command: List[str] = field(default_factory=list)


@dataclass
class WorkspaceConfig:
    """Parsed devtool.toml for one workspace."""

    root: Path
    name: str = ""
    monitor_depth: int = DEFAULT_MONITOR_DEPTH
    plugins: List[PluginSource] = field(default_factory=list)


def load_workspace_config(root: Path) -> Optional[WorkspaceConfig]:
    """Parse devtool.toml at *root* if present; None if absent or unreadable."""
    root = Path(root)
    path = root / WORKSPACE_CONFIG_FILENAME
    if not path.exists():
        return None
    try:
        import tomllib

        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None

    ws = data.get("workspace", {})
    sources: List[PluginSource] = []
    for raw in data.get("plugin", []) or data.get("plugins", []):
        name = raw.get("name", "")
        manifest = raw.get("manifest")
        entry = raw.get("entry", {}) or {}
        command = entry.get("command", []) or []
        sources.append(
            PluginSource(
                name=name,
                manifest=Path(root / manifest) if manifest else None,
                python_module=entry.get("python_module", "") or "",
                command=list(command),
            )
        )
    return WorkspaceConfig(
        root=root,
        name=ws.get("name", ""),
        monitor_depth=ws.get("monitor_depth", DEFAULT_MONITOR_DEPTH),
        plugins=sources,
    )


# ---------------------------------------------------------------------------
# Merged plugin-manifest discovery
# ---------------------------------------------------------------------------

def discover_plugin_sources(
    root: Optional[Path] = None,
    global_dir: Optional[Path] = None,
    in_tree_dir: Optional[Path] = None,
) -> List[Any]:
    """Return the merged plugin sources: manifest paths (Path) or inline
    entry manifests (PluginManifest).

    Order: global dir, in-tree host pack, workspace-declared. Workspace
    entries override earlier same-name sources. Inline entries (no manifest
    file) are synthesized into PluginManifest objects.
    """
    from .plugins import PluginEntry, PluginManifest, load_manifest

    candidates: List[Any] = []
    seen_names: set[str] = set()

    def _manifest_name(manifest: Path) -> str:
        try:
            return load_manifest(manifest).name
        except Exception:
            stem = manifest.stem
            return stem[:-7] if stem.endswith(".plugin") else stem

    def _add_path(manifest: Path) -> None:
        name = _manifest_name(manifest)
        seen_names.add(name)
        candidates.append(manifest)

    for directory in (global_dir, in_tree_dir):
        if directory is None or not Path(directory).is_dir():
            continue
        for manifest in sorted(Path(directory).glob("*.plugin.json")):
            _add_path(manifest)

    config = load_workspace_config(root) if root is not None else None
    if config is not None:
        for source in config.plugins:
            if source.name and source.name in seen_names:
                # workspace overrides global/in-tree same-name plugins
                candidates = [
                    c
                    for c in candidates
                    if (_manifest_name(c) if isinstance(c, Path) else c.name) != source.name
                ]
            if source.manifest is not None and source.manifest.is_file():
                _add_path(source.manifest)
            elif source.python_module or source.command:
                manifest = PluginManifest(
                    name=source.name or "workspace-plugin",
                    version="0.0.0",
                    entry=PluginEntry(
                        python_module=source.python_module,
                        command=tuple(source.command),
                    ),
                )
                candidates.append(manifest)

    return candidates


__all__ = [
    "DEFAULT_MONITOR_DEPTH",
    "PluginSource",
    "STATE_FILENAME",
    "WORKSPACE_CONFIG_FILENAME",
    "WorkspaceConfig",
    "config_dir",
    "discover_plugin_sources",
    "global_plugins_dir",
    "load_last_workspace",
    "load_workspace_config",
    "save_last_workspace",
    "state_path",
]
