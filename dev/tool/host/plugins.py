"""Plugin protocol: the data contract the host and plugins share (v2, #410).

A plugin is declared by a JSON/TOML manifest (plugin.json) -- the manifest is
the single discovery contract (D42). The Python dataclasses below are the
host's parsed *view* of that manifest, not a second source of truth.

A plugin object exposes:
- manifest -- a PluginManifest (name, version, description, surfaces,
  configurable channels, entry selectors).
- artifacts(store) -- returns the plugin's Artifact objects for the current
  workspace.

Entry selectors (D52 / Grok lock #8):
- python_module -- "pkg.module:attr" imported in-process (host-shipped plugins
  that do not import this monorepo).
- command -- an argv list; the host spawns it and appends "--stdio" (the
  language-neutral path; non-Python plugins).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

MANIFEST_SCHEMA = "devtool.plugin.manifest"
MANIFEST_SCHEMA_VERSION = 1


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

    kind: str  # core: session | investigation | image | metric | report | file; else plugin-owned
    name: str
    path: Optional[Path] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginEntry:
    """Runtime selectors (one or both may be set)."""

    python_module: str = ""  # "pkg.module:attr"
    command: Tuple[str, ...] = ()  # argv; host appends "--stdio"


@dataclass(frozen=True)
class PluginManifest:
    """Static declaration of a plugin's identity and surface area."""

    name: str
    version: str  # plugin version (e.g. "0.1.0")
    description: str = ""
    surfaces: Tuple[Surface, ...] = ()
    channels: Tuple[Channel, ...] = ()
    entry_point: str = ""  # legacy dotted "pkg.module:obj"
    entry: PluginEntry = field(default_factory=PluginEntry)
    schema: str = MANIFEST_SCHEMA
    schema_version: int = MANIFEST_SCHEMA_VERSION

    def surface_names(self) -> Tuple[str, ...]:
        return tuple(s.name for s in self.surfaces)

    def channel_keys(self) -> Tuple[str, ...]:
        return tuple(c.key for c in self.channels)

    def effective_entry(self) -> PluginEntry:
        """entry if set, else derive from the legacy entry_point field."""
        if self.entry.python_module or self.entry.command:
            return self.entry
        if self.entry_point:
            return PluginEntry(python_module=self.entry_point)
        return PluginEntry()

    # ------------------------------------------------------------------
    # JSON round-trip (the manifest file is the source of truth)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        entry = self.effective_entry()
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "surfaces": [
                {"name": s.name, "description": s.description} for s in self.surfaces
            ],
            "channels": [
                {
                    "key": c.key,
                    "label": c.label,
                    "description": c.description,
                    "default_enabled": c.default_enabled,
                    "retention": c.retention,
                }
                for c in self.channels
            ],
            "entry": {
                "python_module": entry.python_module or None,
                "command": list(entry.command) or None,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        entry = data.get("entry") or {}
        return cls(
            name=data["name"],
            version=data.get("version", ""),
            description=data.get("description", ""),
            surfaces=tuple(Surface(**s) for s in data.get("surfaces", [])),
            channels=tuple(Channel(**c) for c in data.get("channels", [])),
            entry=PluginEntry(
                python_module=entry.get("python_module") or "",
                command=tuple(entry.get("command") or ()),
            ),
            schema=data.get("schema", MANIFEST_SCHEMA),
            schema_version=data.get("schema_version", MANIFEST_SCHEMA_VERSION),
        )


class Plugin(Protocol):
    """Structural contract for a loaded plugin instance."""

    manifest: PluginManifest

    def artifacts(self, store: Any) -> List[Artifact]: ...


# ---------------------------------------------------------------------------
# Manifest file I/O + command-argv helper
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "plugin.json"


def load_manifest(path: Path) -> PluginManifest:
    """Read a plugin.json manifest file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = PluginManifest.from_dict(data)
    if manifest.schema != MANIFEST_SCHEMA:
        raise ValueError(
            f"unsupported plugin manifest schema {manifest.schema!r} "
            f"(expected {MANIFEST_SCHEMA!r}) in {path}"
        )
    if manifest.schema_version > MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"plugin manifest {manifest.name!r} schema_version "
            f"{manifest.schema_version} is newer than host "
            f"{MANIFEST_SCHEMA_VERSION}"
        )
    return manifest


def write_manifest(path: Path, manifest: PluginManifest) -> Path:
    """Write a plugin.json manifest file (used by plugins/tests)."""
    path = Path(path)
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + chr(10), encoding="utf-8")
    return path


def build_command_argv(manifest: PluginManifest) -> List[str]:
    """D52 / Grok lock #8: the command entry's argv; the host appends
    "--stdio" so the plugin speaks JSON-RPC over stdio."""
    entry = manifest.effective_entry()
    if not entry.command:
        raise ValueError(f"plugin {manifest.name!r} has no command entry")
    return list(entry.command) + ["--stdio"]


__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA",
    "MANIFEST_SCHEMA_VERSION",
    "Artifact",
    "Channel",
    "Plugin",
    "PluginEntry",
    "PluginManifest",
    "Surface",
    "build_command_argv",
    "load_manifest",
    "write_manifest",
]
