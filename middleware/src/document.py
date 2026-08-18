"""Versioned, deterministic HIE document model.

The model deliberately treats a still image as a one-frame sequence.  UIs can
therefore share document and undo/redo code when multi-frame editing arrives.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, Generic, TypeVar


SCHEMA_VERSION = 1


class DocumentSchemaError(ValueError):
    """Raised when serialized HIE document data is invalid or unsupported."""


@dataclass(frozen=True)
class Frame:
    source: str
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FrameSequence:
    frames: tuple[Frame, ...]
    fps: float = 0.0

    def __post_init__(self) -> None:
        if not self.frames:
            raise DocumentSchemaError("a frame sequence must contain at least one frame")
        if self.fps < 0:
            raise DocumentSchemaError("sequence fps cannot be negative")

    @classmethod
    def still(cls, source: str, metadata: dict[str, Any] | None = None) -> "FrameSequence":
        return cls((Frame(source=source, metadata=metadata or {}),))


@dataclass(frozen=True)
class Mask:
    source: str
    inverted: bool = False
    feather_px: float = 0.0


@dataclass(frozen=True)
class Modifier:
    id: str
    operation: str
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True)
class Layer:
    id: str
    name: str
    sequence: FrameSequence
    opacity: float = 1.0
    blend_mode: str = "normal"
    masks: tuple[Mask, ...] = ()
    modifiers: tuple[Modifier, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise DocumentSchemaError(f"layer {self.id!r} opacity must be between 0 and 1")


@dataclass(frozen=True)
class ModifierEdge:
    source: str
    target: str


@dataclass(frozen=True)
class Document:
    document_id: str
    sequence: FrameSequence
    layers: tuple[Layer, ...] = ()
    edges: tuple[ModifierEdge, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        layer_ids = [layer.id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise DocumentSchemaError("layer IDs must be unique")

        modifier_ids = [modifier.id for layer in self.layers for modifier in layer.modifiers]
        if len(modifier_ids) != len(set(modifier_ids)):
            raise DocumentSchemaError("modifier IDs must be unique")
        known = set(modifier_ids)
        adjacency: dict[str, set[str]] = {node: set() for node in known}
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise DocumentSchemaError(f"modifier edge references an unknown node: {edge}")
            adjacency[edge.source].add(edge.target)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise DocumentSchemaError("modifier graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for child in sorted(adjacency[node]):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(known):
            visit(node)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def snapshot_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise DocumentSchemaError(
                f"unsupported document schema version {version!r}; expected {SCHEMA_VERSION}"
            )

        def frame(value: dict[str, Any]) -> Frame:
            return Frame(**value)

        def sequence(value: dict[str, Any]) -> FrameSequence:
            return FrameSequence(tuple(frame(item) for item in value["frames"]), value.get("fps", 0.0))

        def modifier(value: dict[str, Any]) -> Modifier:
            return Modifier(**value)

        def layer(value: dict[str, Any]) -> Layer:
            return Layer(
                id=value["id"], name=value["name"], sequence=sequence(value["sequence"]),
                opacity=value.get("opacity", 1.0), blend_mode=value.get("blend_mode", "normal"),
                masks=tuple(Mask(**item) for item in value.get("masks", [])),
                modifiers=tuple(modifier(item) for item in value.get("modifiers", [])),
            )

        return cls(
            document_id=data["document_id"], sequence=sequence(data["sequence"]),
            layers=tuple(layer(item) for item in data.get("layers", [])),
            edges=tuple(ModifierEdge(**item) for item in data.get("edges", [])),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, payload: str) -> "Document":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise DocumentSchemaError("document payload is not valid JSON") from exc
        if not isinstance(data, dict):
            raise DocumentSchemaError("document payload must be a JSON object")
        return cls.from_dict(data)


T = TypeVar("T")


class DocumentHistory(Generic[T]):
    """Immutable snapshot history suitable for UI undo/redo commands.

    Generic over the snapshot type so both Document (still/image editing)
    and Timeline (video editing, Track 05) share the same undo/redo
    mechanism - no parallel history type.
    """

    def __init__(self, initial: T) -> None:
        self._past: list[T] = []
        self._current = initial
        self._future: list[T] = []

    @property
    def current(self) -> T:
        return self._current

    def commit(self, document: T) -> T:
        self._past.append(self._current)
        self._current = document
        self._future.clear()
        return self._current

    def undo(self) -> T:
        if not self._past:
            return self._current
        self._future.append(self._current)
        self._current = self._past.pop()
        return self._current

    def redo(self) -> T:
        if not self._future:
            return self._current
        self._past.append(self._current)
        self._current = self._future.pop()
        return self._current


@dataclass(frozen=True)
class ClipSegment:
    """One ordered source-range reference in a video timeline (Track 05).

    Extends the Frame intent from a single still frame to a time-range
    reference: trim/remove-range/splice all collapse to list edits on a
    Timeline instead of separate mechanisms.
    """

    source_path: str
    in_ms: int = 0
    out_ms: int = 0

    def __post_init__(self) -> None:
        if self.in_ms < 0 or self.out_ms < 0:
            raise DocumentSchemaError("clip segment times cannot be negative")
        if self.out_ms < self.in_ms:
            raise DocumentSchemaError(
                f"clip segment out_ms ({self.out_ms}) < in_ms ({self.in_ms})"
            )

    @property
    def duration_ms(self) -> int:
        return self.out_ms - self.in_ms


@dataclass(frozen=True)
class Timeline:
    """Ordered list of source-range references (Track 05, design note).

    One primitive (list edit) covers every editing operation:

    - Trim start/end     -> adjust in_ms/out_ms of the first/last segment.
    - Remove inner range -> split one segment in two, drop the middle.
    - Splice             -> insert another ClipSegment at a list position.

    Non-destructive by construction: pure metadata (paths + ms ranges); no
    media bytes are touched while editing. Export is the single destructive
    step (main-repo clip_splicer.py).
    """

    segments: tuple[ClipSegment, ...] = ()

    def __post_init__(self) -> None:
        if not self.segments:
            raise DocumentSchemaError("a timeline must contain at least one segment")

    @classmethod
    def from_frames(cls, frames: FrameSequence) -> "Timeline":
        """Adopt an existing FrameSequence as a one-per-frame timeline."""
        return cls(tuple(
            ClipSegment(source_path=f.source, in_ms=0, out_ms=max(f.duration_ms, 1))
            for f in frames.frames
        ))

    def trim(self, start_ms: int, end_ms: int) -> "Timeline":
        """Trim the timeline's global time window to [start_ms, end_ms).

        Cuts the first/last segment boundaries (no new mechanics: adjusting
        segment edges). Times are global; segments before/after the window
        are dropped.
        """
        if start_ms < 0 or end_ms <= start_ms:
            raise DocumentSchemaError("trim requires 0 <= start_ms < end_ms")
        remaining: list[ClipSegment] = []
        global_t = 0
        for seg in self.segments:
            seg_start = global_t
            seg_end = global_t + seg.duration_ms
            global_t = seg_end
            if seg_end <= start_ms or seg_start >= end_ms:
                continue
            in_ms = seg.in_ms + max(0, start_ms - seg_start)
            out_ms = seg.out_ms - max(0, seg_end - end_ms)
            if out_ms > in_ms:
                remaining.append(ClipSegment(seg.source_path, in_ms, out_ms))
        if not remaining:
            raise DocumentSchemaError("trim produced an empty timeline")
        return Timeline(tuple(remaining))

    def remove_range(self, start_ms: int, end_ms: int) -> "Timeline":
        """Remove the global range [start_ms, end_ms), closing the gap.

        Splits the overlapping segment(s) in two and drops the removed
        middle - a list edit, not a separate cut-list mechanism.
        """
        if start_ms < 0 or end_ms <= start_ms:
            raise DocumentSchemaError("remove_range requires 0 <= start_ms < end_ms")
        out: list[ClipSegment] = []
        global_t = 0
        for seg in self.segments:
            seg_start = global_t
            seg_end = global_t + seg.duration_ms
            global_t = seg_end
            if end_ms <= seg_start or start_ms >= seg_end:
                out.append(seg)
                continue
            # Left kept piece.
            if seg_start < start_ms:
                left_out = seg.in_ms + (min(start_ms, seg_end) - seg_start)
                if left_out > seg.in_ms:
                    out.append(ClipSegment(seg.source_path, seg.in_ms, left_out))
            # Right kept piece.
            if seg_end > end_ms:
                right_in = seg.in_ms + (max(end_ms, seg_start) - seg_start)
                if seg.out_ms > right_in:
                    out.append(ClipSegment(seg.source_path, right_in, seg.out_ms))
        if not out:
            raise DocumentSchemaError("remove_range produced an empty timeline")
        return Timeline(tuple(out))

    def splice(self, index: int, segment: ClipSegment) -> "Timeline":
        """Insert *segment* at list position *index* (splice-in more clips)."""
        if index < 0 or index > len(self.segments):
            raise DocumentSchemaError(f"splice index {index} out of range")
        segs = list(self.segments)
        segs.insert(index, segment)
        return Timeline(tuple(segs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [asdict(s) for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Timeline":
        return cls(tuple(
            ClipSegment(**item) for item in data.get("segments", [])
        ))
