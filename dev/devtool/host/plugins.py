"""Plugin protocol: the data contract the host and plugins share.

A plugin is a Python object exposing:

- manifest -- a PluginManifest (name, version, description, surfaces,
  configurable channels, entry point).
- artifacts(store) -- returns the plugin's Artifact objects for the current
  workspace (sessions, investigations, figures, reports, exports).

Discovery (scanning dev/devtool/plugins/ and importing entry points) is the
process-lifecycle slice (Grok). This module only defines the *shape* so both
sides agree without importing each other's machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class Surface:
    """A UI surface a plugin contributes to: cli / tui / web / mcp."""

    name: str
    description: str = ""


@dataclass(frozen=True)
class Channel:
    """A configurable capture channel.

    Plugins *declare* their channels; settings own enablement, retention
    budgets, and privacy defaults. Plugins must not invent hidden
    environment-only switches for these.
    """

    key: str
    label: str
    description: str = ""
    default_enabled: bool = True
    retention: str = "forever"  # "session" | "7d" | "30d" | "forever"


@dataclass(frozen=True)
class Artifact:
    """One named thing a plugin exposes in a workspace."""

    kind: str  # "session" | "investigation" | "figure" | "report" | "export"
    name: str
    path: Optional[Path] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginManifest:
    """Static declaration of a plugin's identity and surface area."""

    name: str
    version: str
    description: str = ""
    surfaces: Tuple[Surface, ...] = ()
    channels: Tuple[Channel, ...] = ()
    entry_point: str = ""  # dotted "pkg.module:obj" the discovery layer loads

    def surface_names(self) -> Tuple[str, ...]:
        return tuple(s.name for s in self.surfaces)

    def channel_keys(self) -> Tuple[str, ...]:
        return tuple(c.key for c in self.channels)


class Plugin(Protocol):
    """Structural contract for a loaded plugin instance."""

    manifest: PluginManifest

    def artifacts(self, store: Any) -> List[Artifact]: ...


__all__ = [
    "Artifact",
    "Channel",
    "Plugin",
    "PluginManifest",
    "Surface",
]
