from dataclasses import dataclass


@dataclass
class NodeData:
    """Represents a node in the graph."""
    node_id: str
    file_path: str
    display_mode: str = "fixed"      # "fixed" | "video_runtime"
    duration_sec: float = 30.0
    pos_x: float = 0.0
    pos_y: float = 0.0
