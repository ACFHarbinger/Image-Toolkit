"""First-party telemetry workbench plugin (Track A reference).

The canonical example of the plugin protocol: a manifest declaring its
surfaces/channels and an artifacts() method listing the workspace's telemetry
sessions as session artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface

MANIFEST = PluginManifest(
    name="telemetry_workbench",
    version="0.1.0",
    description="Telemetry session analysis: timeline, spans, crash bundles.",
    surfaces=(
        Surface("cli", "analyze / list / tail a telemetry session"),
        Surface("tui", "visual timeline / flame / memory / concurrency views"),
    ),
    channels=(
        Channel("telemetry", "session JSONL capture", retention="30d"),
        Channel("crash", "hs_err + gdb post-mortem bundles", retention="forever"),
    ),
    entry_point="devtool.plugins.telemetry_workbench:plugin",
)


class TelemetryWorkbench:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        artifacts: List[Artifact] = []
        for path in store.sessions():
            artifacts.append(
                Artifact(
                    kind="session",
                    name=path.name,
                    path=Path(path),
                    meta={"pid": _pid_from_path(path)},
                )
            )
        for inv in store.list_investigations():
            artifacts.append(
                Artifact(kind="investigation", name=inv.name, path=inv.root)
            )
        return artifacts


def _pid_from_path(path: Path) -> int:
    import re

    m = re.search(r"telemetry-(\d+)\.jsonl$", path.name)
    return int(m.group(1)) if m else 0


plugin = TelemetryWorkbench()
