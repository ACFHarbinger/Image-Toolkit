"""Host process lifecycle, plugin discovery, and view router.

Grok's C1 slice (D17). The store (deepseek) is the data seam; this module
starts a Host, discovers first-party plugins, optionally calls
``plugin.register(host)``, and answers workspace / command-palette queries
without a resident daemon (D24 / D39).
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .plugins import Artifact, Plugin, PluginManifest
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
        """Load first-party plugins from ``devtool.plugins`` (once)."""
        if self._discovered:
            return list(self._plugins)
        seen: set[str] = set()
        for plugin in _first_party_plugins():
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
                    "entry_point": manifest.entry_point,
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


def _first_party_plugins() -> List[Plugin]:
    """Enumerate ``devtool.plugins``: FIRST_PARTY plus any extra modules."""
    import devtool.plugins as pkg

    found: List[Plugin] = []
    seen: set[str] = set()

    for plugin in getattr(pkg, "FIRST_PARTY", ()):
        _remember(found, seen, plugin)

    prefix = pkg.__name__ + "."
    for module_info in pkgutil.iter_modules(pkg.__path__, prefix):
        if module_info.ispkg or module_info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        module = importlib.import_module(module_info.name)
        plugin = getattr(module, "plugin", None) or getattr(module, "PLUGIN", None)
        if plugin is not None:
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
