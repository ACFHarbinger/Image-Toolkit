from __future__ import annotations

from middleware.src.services.wallpaper.graph import monitor_graph


def _params(path: str, update: bool) -> dict:
    return {
        "update": update,
        "path": path,
        "nodes": [
            {"id": "n1", "path": "/wall/a.png", "duration_seconds": 5},
            {"id": "n2", "path": "/wall/b.png", "duration_seconds": 12},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
        "end_behavior": "solid",
        "end_color": "#112233",
    }


def test_graph_round_trip_uses_only_the_caller_path(tmp_path) -> None:
    path = tmp_path / "graph.json"
    saved = monitor_graph(_params(str(path), True))
    assert saved["error"] == ""
    assert saved["end_behavior"] == "solid"
    loaded = monitor_graph({"update": False, "path": str(path)})
    assert loaded["error"] == ""
    assert loaded["nodes"] == _params(str(path), True)["nodes"]
    assert loaded["edges"] == [{"source": "n1", "target": "n2"}]
    assert loaded["end_color"] == "#112233"
    assert path.is_file()


def test_graph_does_not_create_a_missing_parent(tmp_path) -> None:
    missing = tmp_path / "absent" / "graph.json"
    result = monitor_graph(_params(str(missing), True))
    assert result["error"] == "output directory is missing"
    assert not missing.exists()
    assert not missing.parent.exists()


def test_bad_edge_does_not_write(tmp_path) -> None:
    path = tmp_path / "graph.json"
    params = _params(str(path), True)
    params["edges"] = [{"source": "n1", "target": "missing"}]
    result = monitor_graph(params)
    assert result["error"] == "edge endpoint is missing"
    assert not path.exists()


def test_load_missing_file(tmp_path) -> None:
    result = monitor_graph({"update": False, "path": str(tmp_path / "missing.json")})
    assert result["error"] == "not a file"
    assert result["nodes"] == []
    assert result["end_behavior"] == "repeat"
