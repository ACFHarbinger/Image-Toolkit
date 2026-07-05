from dataclasses import dataclass


@dataclass
class EdgeData:
    """Represents a directed edge in the graph."""
    edge_id: int
    source_id: str
    target_id: str
    # Number of times the target node is repeated back-to-back in the
    # traversal/queue when this edge is taken. Lets a single edge (in
    # particular a self-edge) stand in for N sequential duplicate edges.
    repeat_count: int = 1
