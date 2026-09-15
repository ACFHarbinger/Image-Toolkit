"""#396 research plugin: descriptive failure signals from host sessions."""

from __future__ import annotations

from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..research.failure_analysis import shannon_entropy

MANIFEST = PluginManifest(
    name="failure_analysis",
    version="0.1.0",
    description="Research-only descriptive information-theory analysis over existing host evidence.",
    surfaces=(Surface("cli", "Evidence summaries; no causal conclusions"),),
    channels=(Channel("evidence", "Existing JSONL or Parquet evidence", retention="forever"),),
    entry_point="tool.plugins.failure_analysis:plugin",
)


class FailureAnalysisPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        artifacts: List[Artifact] = []
        for path in store.sessions():
            session = store.open_session(path)
            categories = [event.get("category", "") for event in session.events]
            artifacts.append(Artifact(
                kind="report", name=f"failure-signals:{path.name}", path=path,
                meta={"research": True, "method": "descriptive", "event_count": len(session.events),
                      "category_entropy_bits": shannon_entropy(categories)},
            ))
        return artifacts


plugin = FailureAnalysisPlugin()
