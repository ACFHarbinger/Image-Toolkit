"""Versioned, deterministic HIE document model.

The model deliberately treats a still image as a one-frame sequence.  UIs can
therefore share document and undo/redo code when multi-frame editing arrives.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


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


class DocumentHistory:
    """Immutable snapshot history suitable for UI undo/redo commands."""

    def __init__(self, initial: Document) -> None:
        self._past: list[Document] = []
        self._current = initial
        self._future: list[Document] = []

    @property
    def current(self) -> Document:
        return self._current

    def commit(self, document: Document) -> Document:
        self._past.append(self._current)
        self._current = document
        self._future.clear()
        return self._current

    def undo(self) -> Document:
        if not self._past:
            return self._current
        self._future.append(self._current)
        self._current = self._past.pop()
        return self._current

    def redo(self) -> Document:
        if not self._future:
            return self._current
        self._past.append(self._current)
        self._current = self._future.pop()
        return self._current
