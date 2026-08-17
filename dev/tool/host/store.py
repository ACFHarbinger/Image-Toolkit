"""WorkspaceStore: the durable workspace the host and plugins share.

Owns:
- the workspace root (investigations dir + settings file),
- Investigation persistence,
- Session discovery (re-exported from tool.model),
- loading a plugin by entry point and listing its artifacts.

Process lifecycle / plugin discovery (scanning the plugins dir, importing
entry points, wiring the view router) is the other slice (Grok). This store
is the data-side seam those pieces call into.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from ..model.investigation import Investigation
from ..model.session import Session, discover_sessions
from .plugins import Artifact, Plugin, PluginManifest
from .settings import SETTINGS_FILENAME, Settings


def default_workspace_root() -> Path:
    """Default workspace: the in-repo dev/investigations folder (portable)."""
    return Path(__file__).resolve().parents[2] / "investigations"


@dataclass
class WorkspaceStore:
    """Durable workspace for sessions, investigations, plugins, settings."""

    root: Optional[Path] = None
    telemetry_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        self.root = Path(self.root) if self.root is not None else default_workspace_root()
        self.telemetry_dir = Path(self.telemetry_dir) if self.telemetry_dir else None

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @property
    def settings_path(self) -> Path:
        return self.root / SETTINGS_FILENAME

    def load_settings(self) -> Settings:
        return Settings.load(self.settings_path)

    def save_settings(self, settings: Settings) -> None:
        settings.save(self.settings_path)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def sessions(self, directory: Optional[Path] = None) -> List[Path]:
        return discover_sessions(directory or self.telemetry_dir)

    def open_session(self, path: Path) -> Session:
        return Session.open(path)

    # ------------------------------------------------------------------
    # Investigations
    # ------------------------------------------------------------------

    def create_investigation(self, name: str) -> Investigation:
        return Investigation.create(name, self.root)

    def list_investigations(self) -> List[Investigation]:
        out = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            meta = child / "investigation.json"
            if child.is_dir() and meta.exists():
                out.append(Investigation.open(child))
        return out

    def open_investigation(self, name: str) -> Investigation:
        return Investigation.open(self.root / name)

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def load_plugin(self, entry_point: str) -> Any:
        """Import an entry point ("pkg.module:obj") and return the plugin."""
        module_name, _, attr = entry_point.partition(":")
        module = importlib.import_module(module_name)
        if attr:
            return getattr(module, attr)
        # fall back to a module-level "plugin" or "PLUGIN" object
        return getattr(module, "plugin", None) or module.PLUGIN

    def manifest(self, plugin: Plugin) -> PluginManifest:
        return plugin.manifest

    def list_artifacts(self, plugin: Plugin) -> List[Artifact]:
        """Call plugin.artifacts(store) and return its Artifact list."""
        return list(plugin.artifacts(self))


__all__ = ["WorkspaceStore", "default_workspace_root"]
