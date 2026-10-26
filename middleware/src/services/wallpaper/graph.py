"""Save and load a monitor-display graph at a caller-supplied path (#1107).

The slideshow daemon is not started. A missing parent directory is an error
and is not created.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_END = frozenset({"repeat", "stay", "solid"})


def monitor_graph(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params["path"]))
    if params.get("update"):
        return _write_graph(path, params)
    return _read_graph(path)


def _blank(path: Path, error: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "nodes": [],
        "edges": [],
        "end_behavior": "repeat",
        "end_color": "#000000",
        "error": error,
    }


def _write_graph(path: Path, params: dict[str, Any]) -> dict[str, Any]:
    if path.is_dir() or not path.parent.is_dir():
        return _blank(path, "output directory is missing")
    try:
        graph = _normalize(params)
    except ValueError as exc:
        return _blank(path, str(exc))
    partial: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".partial",
            delete=False,
            encoding="utf-8",
        ) as handle:
            partial = Path(handle.name)
            json.dump(graph, handle, indent=2)
            handle.write("\n")
        os.replace(partial, path)
        partial = None
    except OSError as exc:
        return _blank(path, str(exc))
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
    return {**graph, "path": str(path), "error": ""}


def _read_graph(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _blank(path, "not a file")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("invalid graph")
        graph = _normalize(loaded)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "invalid graph"
        return _blank(path, message)
    return {**graph, "path": str(path), "error": ""}


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("invalid graph")
    normalized_nodes = [_node(item) for item in nodes]
    ids = [item["id"] for item in normalized_nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate node id")
    known = set(ids)
    normalized_edges = [_edge(item, known) for item in edges]
    end_behavior = str(payload.get("end_behavior") or "repeat")
    if end_behavior not in _END:
        raise ValueError("end behavior must be repeat, stay, or solid")
    end_color = payload.get("end_color") or "#000000"
    if not isinstance(end_color, str):
        raise ValueError("end color must be a string")
    return {
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "end_behavior": end_behavior,
        "end_color": end_color,
    }


def _node(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("invalid graph")
    node_id = item.get("id")
    path = item.get("path")
    duration = item.get("duration_seconds")
    if not isinstance(node_id, str) or not node_id or not isinstance(path, str) or not path:
        raise ValueError("invalid graph")
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1 or duration > 86400:
        raise ValueError("duration_seconds is out of range")
    return {"id": node_id, "path": path, "duration_seconds": duration}


def _edge(item: Any, known: set[str]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("invalid graph")
    source = item.get("source")
    target = item.get("target")
    if not isinstance(source, str) or not isinstance(target, str) or source not in known or target not in known:
        raise ValueError("edge endpoint is missing")
    return {"source": source, "target": target}
