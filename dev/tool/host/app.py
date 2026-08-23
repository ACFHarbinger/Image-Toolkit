"""Host process lifecycle, plugin discovery, and view router.

Grok's C1 slice (D17). The store (deepseek) is the data seam; this module
starts a Host, discovers first-party plugins, optionally calls
``plugin.register(host)``, and answers workspace / command-palette queries
without a resident daemon (D24 / D39).
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .plugins import Artifact, Plugin, PluginManifest, load_manifest
from .store import WorkspaceStore

ViewHandler = Callable[..., Any]


@dataclass
class RegisteredView:
    """One named view a plugin (or the host) registered."""

    name: str
    surface: str
    handler: ViewHandler
    plugin: str = ""


class Host:
    """Process-local host. Construct, discover, query; then discard."""

    def __init__(self, store: Optional[WorkspaceStore] = None) -> None:
        self.store = store if store is not None else WorkspaceStore()
        self.settings = self.store.load_settings()
        self._plugins: List[Plugin] = []
        self._views: List[RegisteredView] = []
        self._discovered = False

    def discover(self) -> List[Plugin]:
        """Load first-party plugins from ``tool.plugins`` (once)."""
        if self._discovered:
            return list(self._plugins)
        seen: set[str] = set()
        for plugin in _first_party_plugins(root=self.store.root):
            name = plugin.manifest.name
            if name in seen:
                continue
            seen.add(name)
            self._plugins.append(plugin)
            register = getattr(plugin, "register", None)
            if callable(register):
                register(self)
        self._discovered = True
        return list(self._plugins)

    def plugins(self) -> List[Plugin]:
        if not self._discovered:
            self.discover()
        return list(self._plugins)

    def plugin(self, name: str) -> Optional[Plugin]:
        for plugin in self.plugins():
            if plugin.manifest.name == name:
                return plugin
        return None

    def register_view(
        self,
        name: str,
        handler: ViewHandler,
        *,
        surface: str = "cli",
        plugin: str = "",
    ) -> None:
        self._views.append(
            RegisteredView(name=name, surface=surface, handler=handler, plugin=plugin)
        )

    def views(self, surface: Optional[str] = None) -> List[RegisteredView]:
        if surface is None:
            return list(self._views)
        return [view for view in self._views if view.surface == surface]

    def artifacts(self, plugin_name: Optional[str] = None) -> List[Artifact]:
        out: List[Artifact] = []
        for plugin in self.plugins():
            if plugin_name is not None and plugin.manifest.name != plugin_name:
                continue
            out.extend(self.store.list_artifacts(plugin))
        return out

    def workspace(self) -> Dict[str, Any]:
        """Durable workspace snapshot for the command palette / chooser."""
        plugins = []
        for plugin in self.plugins():
            manifest: PluginManifest = plugin.manifest
            plugins.append(
                {
                    "name": manifest.name,
                    "version": manifest.version,
                    "description": manifest.description,
                    "surfaces": list(manifest.surface_names()),
                    "channels": list(manifest.channel_keys()),
                    "entry_point": manifest.effective_entry().python_module,
                    "command": list(manifest.effective_entry().command) or None,
                }
            )
        sessions = [str(path) for path in self.store.sessions()]
        investigations = [inv.name for inv in self.store.list_investigations()]
        artifacts = [
            {
                "kind": art.kind,
                "name": art.name,
                "path": None if art.path is None else str(art.path),
                "plugin": plugin_name,
            }
            for plugin_name in (p["name"] for p in plugins)
            for art in self.artifacts(plugin_name)
        ]
        return {
            "workspace": str(self.store.root),
            "plugins": plugins,
            "sessions": sessions,
            "investigations": investigations,
            "artifacts": artifacts,
            "views": [
                {"name": v.name, "surface": v.surface, "plugin": v.plugin}
                for v in self._views
            ],
            "settings": {
                "alert_emphasis": self.settings.alert_emphasis,
                "redact_home_paths": self.settings.redact_home_paths,
            },
        }


class _CommandPlugin:
    """A command-entry plugin the host can list but not yet spawn.

    Spawning + JSON-RPC/stdio client is the sidecar slice (#408); until then
    this wrapper lets the host see the plugin and its manifest.
    """

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest

    def artifacts(self, store: Any) -> List[Artifact]:
        return []


def _first_party_plugins(root: Optional[Path] = None) -> List[Plugin]:
    """Enumerate plugin.json manifests manifest-first (#410/#412).

    Merged set = global (~/.config/devtool/plugins) + in-tree host pack +
    workspace-declared (devtool.toml); resolves python_module entries to
    the plugin object; command-only manifests become _CommandPlugin
    wrappers (spawning is #408).
    """
    import tool.plugins as pkg

    from .workspace import discover_plugin_sources, global_plugins_dir

    found: List[Plugin] = []
    seen: set[str] = set()
    plugins_dir = Path(pkg.__file__).resolve().parent

    for source in discover_plugin_sources(
        root=root,
        global_dir=global_plugins_dir(),
        in_tree_dir=plugins_dir,
    ):
        try:
            manifest = source if not isinstance(source, Path) else load_manifest(source)
        except Exception as exc:
            print(
                f"[devtool] skipping bad plugin manifest {source}: {exc}",
                file=sys.stderr,
            )
            continue
        entry = manifest.effective_entry()
        if entry.python_module:
            module_name, _, attr = entry.python_module.partition(":")
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                print(
                    f"[devtool] skipping {manifest.name!r}: cannot import "
                    f"{module_name}: {exc}",
                    file=sys.stderr,
                )
                continue
            plugin = getattr(module, attr or "plugin", None) or getattr(module, "plugin", None)
            if plugin is None:
                continue
            # The JSON manifest is the authoritative declaration; the plugin
            # object supplies the runtime artifacts() implementation.
            import contextlib

            with contextlib.suppress(Exception):
                plugin.manifest = manifest
        else:
            plugin = _CommandPlugin(manifest)
        _remember(found, seen, plugin)
    return found
def _remember(found: List[Plugin], seen: set[str], plugin: Plugin) -> None:
    name = plugin.manifest.name
    if name in seen:
        return
    seen.add(name)
    found.append(plugin)


def discover_plugins(store: Optional[WorkspaceStore] = None) -> List[Plugin]:
    """Convenience: new Host, discover, return plugins."""
    return Host(store=store).discover()


__all__ = ["Host", "RegisteredView", "discover_plugins"]
