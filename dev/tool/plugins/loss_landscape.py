"""First-party ML model & loss-landscape plugin (Track B Phase 2, #394).

Data producer for the host's 3D/2D views: discovers loss surfaces, Hessian
spectra, weight trajectories, and activation atlases exported under
``dev/tool/export/loss_landscape/`` (one JSON file per artifact, written by
the research scaffolding in :mod:`tool.research.loss_landscape`). The heavy
live models (AnimeStitchNet, BiRefNet, LoFTR, DINOv2) are only loaded in
environments that have them; this plugin never imports torch itself — it
charts what was already exported, following the Track B host-attachment row
("future plugin; scoped to live models").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..host.plugins import Artifact, Channel, PluginManifest, Surface

MANIFEST = PluginManifest(
    name="loss_landscape",
    version="0.1.0",
    description=(
        "ML model & loss-landscape visualizer: filter-normalized loss surfaces, "
        "Hessian spectra, weight trajectories, activation atlases (Track B #394)."
    ),
    surfaces=(
        Surface("cli", "summarize exported loss landscapes / spectra / trajectories / atlases"),
        Surface("web", "3D surface, ESD, trajectory, and atlas views chart from exported artifacts"),
    ),
    channels=(
        Channel("loss_surfaces", "filter-normalized loss-surface grids + optimizer trajectories", retention="forever"),
        Channel("hessian_spectra", "Hutchinson trace + SLQ eigenvalue spectral densities", retention="forever"),
        Channel("weight_trajectories", "PCA/t-SNE weight & gradient trajectory projections", retention="forever"),
        Channel("activation_maps", "activation atlas embeddings + attention-map overlays", retention="forever"),
    ),
    entry_point="tool.plugins.loss_landscape:plugin",
)

_KIND_TO_CHANNEL = {
    "loss_surface": "loss_surfaces",
    "hessian_spectrum": "hessian_spectra",
    "weight_trajectory": "weight_trajectories",
    "activation_atlas": "activation_maps",
}

_EXPORT_SUBDIR = Path("dev/tool/export/loss_landscape")


class LossLandscapePlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        """Discover exported loss-landscape artifacts across the workspace."""
        repo_root = Path(getattr(store, "repo_root", Path.cwd()))
        out_dir = repo_root / _EXPORT_SUBDIR
        artifacts: List[Artifact] = []
        if not out_dir.exists():
            return artifacts
        for path in sorted(out_dir.glob("*.json")):
            kind = self._kind_of(path)
            if kind is None:
                continue  # not one of ours (or unparseable) — don't claim it
            artifacts.append(
                Artifact(
                    kind=kind,
                    name=path.name,
                    path=path,
                    meta={"channel": _KIND_TO_CHANNEL.get(kind, "")},
                )
            )
        return artifacts

    @staticmethod
    def _kind_of(path: Path) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                head = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        for key in _KIND_TO_CHANNEL:
            if key in head:
                return key
        return None

    @staticmethod
    def summarize(path: Path) -> Dict[str, Any]:
        """One-screen summary of one exported artifact, for the CLI surface."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "loss_surface" in data or ("alpha_range" in data and "losses" in data):
            surface = data.get("loss_surface", data)
            rows = len(surface.get("losses", []))
            cols = len(surface.get("losses", [[]])[0]) if rows else 0
            flat = [v for row in surface.get("losses", []) for v in row]
            return {
                "kind": "loss_surface",
                "model": surface.get("model_name", "?"),
                "grid": f"{rows}x{cols}",
                "loss_min": round(min(flat), 6) if flat else None,
                "loss_max": round(max(flat), 6) if flat else None,
                "trajectory_points": len(surface.get("trajectory", [])),
            }
        if "hessian_spectrum" in data or "trace_estimate" in data:
            spec = data.get("hessian_spectrum", data)
            return {
                "kind": "hessian_spectrum",
                "model": spec.get("model_name", "?"),
                "trace_estimate": spec.get("trace_estimate"),
                "eigen_min": spec.get("min_eigenvalue"),
                "eigen_max": spec.get("max_eigenvalue"),
                "sharpness": spec.get("sharpness"),
                "probes": spec.get("num_probes"),
            }
        if "weight_trajectory" in data or "points" in data:
            traj = data.get("weight_trajectory", data)
            return {
                "kind": "weight_trajectory",
                "model": traj.get("model_name", "?"),
                "method": traj.get("method"),
                "steps": len(traj.get("points", [])),
            }
        if "activation_atlas" in data or "embedding" in data:
            atlas = data.get("activation_atlas", data)
            return {
                "kind": "activation_atlas",
                "model": atlas.get("model_name", "?"),
                "layer": atlas.get("layer_name", "?"),
                "samples": len(atlas.get("embedding", [])),
                "attention_maps": len(atlas.get("attention", [])),
            }
        return {"kind": "unknown", "keys": sorted(data)[:8]}


plugin = LossLandscapePlugin()


def main(argv=None) -> int:
    """D52 command-plugin entry: python -m tool.plugins.<name> --stdio."""
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
