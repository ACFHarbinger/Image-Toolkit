"""#398 research plugin: static candidate findings, never security verdicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..research.semantic_security import scan_python

MANIFEST = PluginManifest(
    name="semantic_security",
    version="0.1.0",
    description="Research-only static candidate findings; not a CPG/CodeQL engine or v1 scanner.",
    surfaces=(Surface("cli", "Auditable candidate findings"),),
    channels=(Channel("source_candidates", "Static candidate findings", retention="forever"),),
    entry_point="tool.plugins.semantic_security:plugin",
)


class SemanticSecurityPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        root = Path(getattr(store, "repo_root", Path.cwd()))
        artifacts: List[Artifact] = []
        for path in root.glob("backend/**/*.py"):
            findings = scan_python(path)
            if findings:
                artifacts.append(Artifact("report", f"candidate-findings:{path.relative_to(root)}", path,
                    {"research": True, "findings": [f.__dict__ | {"path": str(f.path)} for f in findings]}))
        return artifacts


plugin = SemanticSecurityPlugin()


def main(argv=None) -> int:
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)
