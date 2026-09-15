"""#396 research plugin: descriptive failure signals from host sessions."""

from __future__ import annotations

from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..research.failure_analysis import load_evidence_rows, shannon_entropy

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
        evidence_paths = list(store.sessions())
        telemetry_dir = getattr(store, "telemetry_dir", None)
        if telemetry_dir and telemetry_dir.exists():
            evidence_paths.extend(sorted(telemetry_dir.glob("*.parquet")))
        for path in evidence_paths:
            rows = load_evidence_rows(path)
            categories = [row.get("category", "") for row in rows]
            artifacts.append(Artifact(
                kind="report", name=f"failure-signals:{path.name}", path=path,
                meta={"research": True, "method": "descriptive", "event_count": len(rows),
                      "category_entropy_bits": shannon_entropy(categories)},
            ))
        return artifacts


plugin = FailureAnalysisPlugin()


def main(argv=None) -> int:
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)
