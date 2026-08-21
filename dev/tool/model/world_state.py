"""Persistent on-disk Graph World State model (Issue #419 / D45 / D55 / D57).

Stores 3D node layouts, camera vantage points, layer/tag filters, and
Investigation spatial bookmarks. Persists to a diffable, versioned JSON file
under the workspace root (e.g. `.devtool/world_state.json`), surviving sidecar
restarts and session switches.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORLD_STATE_FILENAME = "world_state.json"
WORLD_STATE_SCHEMA = "devtool.world_state"
WORLD_STATE_VERSION = 1


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CameraBookmark:
    """A 3D spatial viewpoint linked to an Investigation or visual preset."""

    id: str
    label: str
    position: List[float]  # [x, y, z]
    target: List[float]  # [x, y, z]
    fov: float = 45.0
    pinned_node_id: Optional[str] = None
    investigation_id: Optional[str] = None
    created_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraBookmark":
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            position=[float(v) for v in data.get("position", [0.0, 50.0, 100.0])],
            target=[float(v) for v in data.get("target", [0.0, 0.0, 0.0])],
            fov=float(data.get("fov", 45.0)),
            pinned_node_id=data.get("pinned_node_id"),
            investigation_id=data.get("investigation_id"),
            created_at=data.get("created_at", _utcnow_iso()),
        )


@dataclass
class NodeSpatialState:
    """Manual overrides or cached spatial layout coordinates for a node."""

    node_id: str
    position: List[float]  # [x, y, z]
    pinned: bool = False
    visible: bool = True
    custom_color: Optional[str] = None
    cluster_group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeSpatialState":
        return cls(
            node_id=data["node_id"],
            position=[float(v) for v in data.get("position", [0.0, 0.0, 0.0])],
            pinned=bool(data.get("pinned", False)),
            visible=bool(data.get("visible", True)),
            custom_color=data.get("custom_color"),
            cluster_group=data.get("cluster_group"),
        )


@dataclass
class WorldFilterState:
    """Active filters governing node/edge visibility in the 3D scene."""

    show_frontend: bool = True
    show_core: bool = True
    show_native: bool = True
    min_latency_ms: float = 0.0
    min_call_volume: int = 0
    active_tags: List[str] = field(default_factory=list)
    search_query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldFilterState":
        return cls(
            show_frontend=bool(data.get("show_frontend", True)),
            show_core=bool(data.get("show_core", True)),
            show_native=bool(data.get("show_native", True)),
            min_latency_ms=float(data.get("min_latency_ms", 0.0)),
            min_call_volume=int(data.get("min_call_volume", 0)),
            active_tags=list(data.get("active_tags", [])),
            search_query=str(data.get("search_query", "")),
        )


@dataclass
class WorldState:
    """Persistent on-disk state of the 3D runtime-flow world."""

    workspace: str
    schema: str = WORLD_STATE_SCHEMA
    version: int = WORLD_STATE_VERSION
    updated_at: str = field(default_factory=_utcnow_iso)
    camera: CameraBookmark = field(
        default_factory=lambda: CameraBookmark(
            id="default",
            label="Default View",
            position=[0.0, 40.0, 90.0],
            target=[0.0, 0.0, 0.0],
            fov=45.0,
        )
    )
    nodes: Dict[str, NodeSpatialState] = field(default_factory=dict)
    bookmarks: List[CameraBookmark] = field(default_factory=list)
    filters: WorldFilterState = field(default_factory=WorldFilterState)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "workspace": self.workspace,
            "updated_at": self.updated_at,
            "camera": self.camera.to_dict(),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "bookmarks": [b.to_dict() for b in self.bookmarks],
            "filters": self.filters.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldState":
        nodes = {
            k: NodeSpatialState.from_dict(v)
            for k, v in data.get("nodes", {}).items()
        }
        bookmarks = [
            CameraBookmark.from_dict(b) for b in data.get("bookmarks", [])
        ]
        camera_data = data.get("camera")
        camera = (
            CameraBookmark.from_dict(camera_data)
            if camera_data
            else CameraBookmark("default", "Default View", [0.0, 40.0, 90.0], [0.0, 0.0, 0.0])
        )
        filters_data = data.get("filters")
        filters = (
            WorldFilterState.from_dict(filters_data)
            if filters_data
            else WorldFilterState()
        )

        return cls(
            workspace=data.get("workspace", ""),
            schema=data.get("schema", WORLD_STATE_SCHEMA),
            version=int(data.get("version", WORLD_STATE_VERSION)),
            updated_at=data.get("updated_at", _utcnow_iso()),
            camera=camera,
            nodes=nodes,
            bookmarks=bookmarks,
            filters=filters,
        )

    def save(self, workspace_root: Path | str) -> Path:
        """Atomically persist world state to .devtool/world_state.json."""
        root = Path(workspace_root)
        devtool_dir = root / ".devtool"
        devtool_dir.mkdir(parents=True, exist_ok=True)
        out_path = devtool_dir / WORLD_STATE_FILENAME
        self.updated_at = _utcnow_iso()
        self.workspace = str(root.resolve())

        temp_path = out_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        temp_path.replace(out_path)
        return out_path

    @classmethod
    def load(cls, workspace_root: Path | str) -> "WorldState":
        """Load world state from .devtool/world_state.json, or create a default instance."""
        root = Path(workspace_root)
        state_path = root / ".devtool" / WORLD_STATE_FILENAME
        if not state_path.exists():
            return cls(workspace=str(root.resolve()))

        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception:
            return cls(workspace=str(root.resolve()))

    # ------------------------------------------------------------------
    # Bookmark & Annotation Linking
    # ------------------------------------------------------------------

    def add_bookmark(
        self,
        label: str,
        position: List[float],
        target: List[float],
        investigation_id: Optional[str] = None,
        pinned_node_id: Optional[str] = None,
        fov: float = 45.0,
    ) -> CameraBookmark:
        """Create and store a camera bookmark."""
        import uuid

        bm = CameraBookmark(
            id=f"bm-{uuid.uuid4().hex[:8]}",
            label=label,
            position=position,
            target=target,
            fov=fov,
            pinned_node_id=pinned_node_id,
            investigation_id=investigation_id,
        )
        self.bookmarks.append(bm)
        return bm

    def update_node_position(
        self, node_id: str, x: float, y: float, z: float, pinned: bool = True
    ) -> None:
        """Update or cache a specific node's 3D spatial coordinate."""
        if node_id in self.nodes:
            self.nodes[node_id].position = [x, y, z]
            self.nodes[node_id].pinned = pinned
        else:
            self.nodes[node_id] = NodeSpatialState(
                node_id=node_id, position=[x, y, z], pinned=pinned
            )
