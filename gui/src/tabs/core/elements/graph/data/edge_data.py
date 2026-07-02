from dataclasses import dataclass

@dataclass
class EdgeData:
    """Represents a directed edge in the graph."""
    edge_id: int
    source_id: str
    target_id: str
