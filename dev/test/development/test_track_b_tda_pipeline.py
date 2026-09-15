"""Tests for TDA Pipeline plugin (Track B Phase 10, issue #402)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tool.model.tda_pipeline import (
    BettiCurve,
    PersistenceDiagram,
    PersistencePoint,
    TDAFingerprint,
)
from tool.plugins.tda_pipeline import plugin
from tool.research.tda_pipeline import (
    compute_betti_curves,
    compute_distance_matrix,
    compute_vietoris_rips_persistence,
    euclidean_distance,
    extract_fingerprint_from_call_graph,
)


class TestPersistencePoint:
    def test_persistence_finite(self):
        p = PersistencePoint(birth=1.0, death=3.0, dimension=0)
        assert p.persistence == 2.0
        assert not p.is_essential

    def test_persistence_infinite(self):
        p = PersistencePoint(birth=1.0, death=float("inf"), dimension=0)
        assert p.persistence == float("inf")
        assert p.is_essential

    def test_round_trip(self):
        p = PersistencePoint(birth=1.5, death=4.5, dimension=1)
        data = p.to_dict()
        restored = PersistencePoint.from_dict(data)
        assert restored.birth == p.birth
        assert restored.death == p.death
        assert restored.dimension == p.dimension

    def test_round_trip_infinite(self):
        p = PersistencePoint(birth=0.0, death=float("inf"), dimension=0)
        data = p.to_dict()
        assert data["death"] == "inf"
        restored = PersistencePoint.from_dict(data)
        assert restored.is_essential


class TestPersistenceDiagram:
    def test_empty_diagram(self):
        d = PersistenceDiagram(dimension=0)
        assert d.betti_number == 0
        assert d.total_persistence == 0.0
        assert d.max_persistence == 0.0

    def test_betti_number(self):
        d = PersistenceDiagram(
            dimension=0,
            points=[
                PersistencePoint(0.0, 1.0, 0),  # died
                PersistencePoint(0.0, float("inf"), 0),  # essential
                PersistencePoint(0.5, float("inf"), 0),  # essential
            ],
        )
        assert d.betti_number == 2  # 2 essential features

    def test_total_persistence(self):
        d = PersistenceDiagram(
            dimension=0,
            points=[
                PersistencePoint(0.0, 2.0, 0),  # persistence = 2
                PersistencePoint(1.0, 4.0, 0),  # persistence = 3
                PersistencePoint(0.0, float("inf"), 0),  # infinite, not counted
            ],
        )
        assert d.total_persistence == 5.0

    def test_round_trip(self):
        d = PersistenceDiagram(
            dimension=1,
            points=[
                PersistencePoint(1.0, 3.0, 1),
                PersistencePoint(2.0, float("inf"), 1),
            ],
        )
        data = d.to_dict()
        restored = PersistenceDiagram.from_dict(data)
        assert restored.dimension == d.dimension
        assert len(restored.points) == 2


class TestBettiCurve:
    def test_empty_curve(self):
        b = BettiCurve(dimension=0)
        assert b.betti_at(0.5) == 0

    def test_betti_at(self):
        b = BettiCurve(
            dimension=0,
            filtration_values=[0.0, 1.0, 2.0, 3.0],
            betti_values=[3, 2, 1, 1],
        )
        assert b.betti_at(0.5) == 3
        assert b.betti_at(1.5) == 2
        assert b.betti_at(2.5) == 1
        assert b.betti_at(5.0) == 1  # beyond max


class TestTDAFingerprint:
    def test_empty_fingerprint(self):
        f = TDAFingerprint(module_id="test")
        assert f.total_betti_0 == 0
        assert f.total_betti_1 == 0
        assert f.total_betti_2 == 0

    def test_summary(self):
        f = TDAFingerprint(
            module_id="test",
            diagrams=[
                PersistenceDiagram(
                    dimension=0,
                    points=[PersistencePoint(0.0, float("inf"), 0)],
                ),
                PersistenceDiagram(
                    dimension=1,
                    points=[
                        PersistencePoint(1.0, 3.0, 1),
                        PersistencePoint(2.0, float("inf"), 1),
                    ],
                ),
            ],
        )
        summary = f.to_dict()["summary"]
        assert summary["total_betti_0"] == 1
        assert summary["total_betti_1"] == 1
        assert summary["total_betti_2"] == 0


class TestDistanceMatrix:
    def test_euclidean_distance(self):
        assert euclidean_distance([0, 0], [3, 4]) == 5.0

    def test_distance_matrix(self):
        points = [[0, 0], [1, 0], [0, 1]]
        dm = compute_distance_matrix(points)
        assert dm[0][0] == 0.0
        assert dm[0][1] == 1.0
        assert dm[0][2] == 1.0
        assert dm[1][2] == pytest.approx(2**0.5)


class TestVietorisRips:
    def test_single_point(self):
        diagrams = compute_vietoris_rips_persistence([[0, 0]], max_dimension=1)
        assert len(diagrams) == 2
        assert len(diagrams[0].points) == 1  # one essential component
        assert diagrams[0].points[0].is_essential

    def test_two_points(self):
        diagrams = compute_vietoris_rips_persistence([[0, 0], [1, 0]], max_dimension=1)
        # Two points: one component born at 0, one dies when they merge at distance 1
        assert len(diagrams[0].points) >= 1

    def test_empty_point_cloud(self):
        diagrams = compute_vietoris_rips_persistence([], max_dimension=1)
        assert len(diagrams) == 2
        assert all(len(d.points) == 0 for d in diagrams)


class TestBettiCurves:
    def test_from_empty_diagram(self):
        diagrams = [PersistenceDiagram(dimension=0)]
        curves = compute_betti_curves(diagrams)
        assert len(curves) == 1
        assert len(curves[0].filtration_values) == 0

    def test_from_diagram_with_points(self):
        diagrams = [
            PersistenceDiagram(
                dimension=0,
                points=[
                    PersistencePoint(0.0, 2.0, 0),
                    PersistencePoint(0.0, float("inf"), 0),
                ],
            ),
        ]
        curves = compute_betti_curves(diagrams, num_samples=10)
        assert len(curves) == 1
        assert len(curves[0].filtration_values) == 10


class TestCallGraphFingerprint:
    def test_empty_graph(self):
        fp = extract_fingerprint_from_call_graph("test", [])
        assert fp.module_id == "test"
        assert len(fp.diagrams) == 0 or all(len(d.points) == 0 for d in fp.diagrams)

    def test_simple_graph(self):
        edges = [("a", "b"), ("b", "c"), ("a", "c")]
        fp = extract_fingerprint_from_call_graph("test_module", edges)
        assert fp.module_id == "test_module"
        assert len(fp.diagrams) >= 1


class TestCLI:
    def test_demo_command(self, capsys):
        result = plugin(["demo"])
        assert result == 0
        captured = capsys.readouterr()
        assert "TDA Fingerprint: demo_point_cloud" in captured.out

    def test_demo_json_out(self, tmp_path: Path):
        json_out = tmp_path / "fingerprint.json"
        result = plugin(["demo", "--json-out", str(json_out)])
        assert result == 0
        assert json_out.exists()
        data = json.loads(json_out.read_text())
        assert "module_id" in data
        assert data["module_id"] == "demo_point_cloud"

    def test_compute_command(self, tmp_path: Path, capsys):
        call_graph = tmp_path / "graph.json"
        call_graph.write_text(json.dumps({"edges": [{"src": "a", "dst": "b"}]}))

        result = plugin(["compute", str(call_graph), "--module-id", "test_mod"])
        assert result == 0
        captured = capsys.readouterr()
        assert "TDA Fingerprint: test_mod" in captured.out


class TestPluginManifest:
    def test_manifest_valid(self):
        manifest_path = Path(__file__).parent.parent.parent / "tool" / "plugins" / "tda_pipeline.plugin.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["schema"] == "devtool.plugin.manifest"
        assert manifest["name"] == "tda_pipeline"
        assert len(manifest["channels"]) == 1
        assert manifest["channels"][0]["key"] == "tda_fingerprints"
