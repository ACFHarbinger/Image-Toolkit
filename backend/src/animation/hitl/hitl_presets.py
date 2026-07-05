"""
Per-test HITL preset system. Saves/loads manual corrections for specific test datasets.
Preset files live in ASP_HITL_PRESET_DIR (default ~/.image-toolkit/hitl_presets/).
§3.16B
"""
from __future__ import annotations

import dataclasses
import json
import os
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

__all__ = [
    "HitlPreset",
    "load_hitl_preset",
    "apply_hitl_preset",
    "save_hitl_preset",
    "list_hitl_presets",
    "HITL_PRESET_DIR_DEFAULT",
]

HITL_PRESET_DIR_DEFAULT = str(Path.home() / ".image-toolkit" / "hitl_presets")

_PRESET_DIR = os.environ.get("ASP_HITL_PRESET_DIR", HITL_PRESET_DIR_DEFAULT)


@dataclasses.dataclass
class HitlPreset:
    """Manual correction preset for a specific test dataset."""
    test_name: str
    # Frame indices to force-keep (overrides smart selection)
    forced_frame_indices: List[int] = dataclasses.field(default_factory=list)
    # Edge pairs to drop: list of (src_idx, dst_idx)
    drop_edges: List[Tuple[int, int]] = dataclasses.field(default_factory=list)
    # Forced boundary positions in canvas pixels
    forced_boundaries: List[int] = dataclasses.field(default_factory=list)
    # Force scroll axis: "vertical", "horizontal", or "" (auto)
    scroll_axis_override: str = ""
    # Force SCANS fallback
    force_scans: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "HitlPreset":
        d = dict(d)
        d["drop_edges"] = [tuple(e) for e in d.get("drop_edges", [])]
        return cls(**d)


def _preset_path(test_name: str, base_dir: Optional[str] = None) -> Path:
    directory = Path(base_dir or _PRESET_DIR)
    return directory / f"{test_name}.json"


def load_hitl_preset(test_name: str, base_dir: Optional[str] = None) -> Optional[HitlPreset]:
    """Load a HITL preset for *test_name*. Returns None if no preset exists."""
    path = _preset_path(test_name, base_dir)
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return HitlPreset.from_dict(json.load(f))
    except Exception as exc:
        warnings.warn(f"hitl_presets: failed to load {path}: {exc}", stacklevel=2)
        return None


def save_hitl_preset(test_name: str, preset: HitlPreset, base_dir: Optional[str] = None) -> None:
    """Persist *preset* to disk."""
    path = _preset_path(test_name, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(preset.to_dict(), f, indent=2)


def list_hitl_presets(base_dir: Optional[str] = None) -> List[str]:
    """Return sorted list of test names that have a saved preset."""
    directory = Path(base_dir or _PRESET_DIR)
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def apply_hitl_preset(pipeline_state: dict, preset: HitlPreset) -> dict:
    """
    Apply *preset* overrides to *pipeline_state* (mutates and returns it).

    pipeline_state keys used:
      - "edges": List[dict] with "src"/"dst" keys
      - "boundaries": List[int]
      - "scroll_axis": str
      - "force_scans": bool
    """
    if preset.force_scans:
        pipeline_state["force_scans"] = True
        return pipeline_state

    if preset.drop_edges and "edges" in pipeline_state:
        drop_set = {(int(s), int(d)) for s, d in preset.drop_edges}
        pipeline_state["edges"] = [
            e for e in pipeline_state["edges"]
            if (int(e.get("src", -1)), int(e.get("dst", -1))) not in drop_set
        ]

    if preset.forced_boundaries:
        pipeline_state["boundaries"] = list(preset.forced_boundaries)

    if preset.scroll_axis_override:
        pipeline_state["scroll_axis"] = preset.scroll_axis_override

    return pipeline_state
