"""Evaluation data schema: bounding boxes, edges, and the per-test evaluation entry.

Preserves the original ``{test: {asp, simple, notes}}`` JSON keys so
``bench_anime_stitch.py``'s ``_load_human_evaluations()`` keeps reading this file
unmodified (it only ever does ``.get("asp")`` / ``.get("simple")``); the new
``bboxes``/``edges`` keys are purely additive.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Optional


@dataclasses.dataclass
class BoundingBox:
    """A user-drawn failure-mode region, in image-normalized [0, 1] coords."""

    image: str  # "asp" | "simple" | "ground_truth"
    x: float
    y: float
    w: float
    h: float
    label: str = ""

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "BoundingBox":
        return BoundingBox(
            image=d["image"], x=d["x"], y=d["y"], w=d["w"], h=d["h"],
            label=d.get("label", ""),
        )


@dataclasses.dataclass
class EdgePoint:
    image: str
    x: float
    y: float


@dataclasses.dataclass
class Edge:
    """A misalignment/comparison link between a point (or bbox center) in
    one displayed image and a point in another."""

    a: EdgePoint
    b: EdgePoint
    label: str = ""

    def to_dict(self) -> Dict:
        return {
            "a": dataclasses.asdict(self.a),
            "b": dataclasses.asdict(self.b),
            "label": self.label,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Edge":
        return Edge(
            a=EdgePoint(**d["a"]), b=EdgePoint(**d["b"]), label=d.get("label", ""),
        )


@dataclasses.dataclass
class RatingEntry:
    asp: Optional[int] = None
    simple: Optional[int] = None
    notes: str = ""
    bboxes: List[BoundingBox] = dataclasses.field(default_factory=list)
    edges: List[Edge] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "asp": self.asp,
            "simple": self.simple,
            "notes": self.notes,
            "bboxes": [b.to_dict() for b in self.bboxes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @staticmethod
    def from_dict(d: Dict) -> "RatingEntry":
        return RatingEntry(
            asp=d.get("asp"),
            simple=d.get("simple"),
            notes=d.get("notes", ""),
            bboxes=[BoundingBox.from_dict(b) for b in d.get("bboxes", [])],
            edges=[Edge.from_dict(e) for e in d.get("edges", [])],
        )


def load_evaluations(path: str) -> Dict[str, RatingEntry]:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        raw = json.load(fh)
    return {name: RatingEntry.from_dict(entry) for name, entry in raw.items()}


def save_evaluations(path: str, evaluations: Dict[str, RatingEntry]) -> None:
    doc = {name: entry.to_dict() for name, entry in evaluations.items()}
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    os.replace(tmp_path, path)  # atomic — a mid-write crash never corrupts the real file
