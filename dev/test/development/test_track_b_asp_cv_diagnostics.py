"""Tests for ASP CV Diagnostics plugin (Track B Phase 3, issue #395)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tool.model.asp_cv_diagnostics import (
    BundleAdjustmentResiduals,
    FeatureMatch,
    Keypoint,
    MatchGeometry,
    SeamDiagnostic,
    SeamFrequencyProfile,
    SeamGradientCoherence,
    StageDiagnosticReport,
)
from tool.plugins.asp_cv_diagnostics import run_cli
from tool.research.asp_cv_diagnostics import (
    build_diagnostic_report,
    discover_telemetry_files,
    extract_metrics,
    extract_spans,
    parse_telemetry_jsonl,
)


class TestKeypoint:
    def test_round_trip(self):
        kp = Keypoint(x=10.5, y=20.3, scale=2.0, orientation=0.5, response=100.0)
        data = kp.to_dict()
        restored = Keypoint.from_dict(data)
        assert restored.x == kp.x
        assert restored.y == kp.y
        assert restored.scale == kp.scale
        assert restored.orientation == kp.orientation
        assert restored.response == kp.response


class TestFeatureMatch:
    def test_round_trip(self):
        match = FeatureMatch(query_idx=0, train_idx=5, distance=0.8, is_inlier=True)
        data = match.to_dict()
        restored = FeatureMatch.from_dict(data)
        assert restored.query_idx == match.query_idx
        assert restored.train_idx == match.train_idx
        assert restored.distance == match.distance
        assert restored.is_inlier == match.is_inlier


class TestMatchGeometry:
    def test_inlier_ratio_empty(self):
        mg = MatchGeometry(frame_a_id="a", frame_b_id="b")
        assert mg.inlier_ratio == 0.0

    def test_inlier_ratio_computed(self):
        mg = MatchGeometry(
            frame_a_id="a",
            frame_b_id="b",
            matches=[
                FeatureMatch(0, 0, 0.5, True),
                FeatureMatch(1, 1, 0.6, True),
                FeatureMatch(2, 2, 0.9, False),
            ],
            inlier_count=2,
        )
        assert mg.inlier_ratio == pytest.approx(2 / 3)

    def test_round_trip(self):
        mg = MatchGeometry(
            frame_a_id="frame_001",
            frame_b_id="frame_002",
            keypoints_a=[Keypoint(10, 20)],
            keypoints_b=[Keypoint(15, 25)],
            matches=[FeatureMatch(0, 0, 0.5, True)],
            inlier_count=1,
            residual_mean=1.5,
            residual_std=0.3,
            residual_max=2.0,
        )
        data = mg.to_dict()
        restored = MatchGeometry.from_dict(data)
        assert restored.frame_a_id == mg.frame_a_id
        assert restored.frame_b_id == mg.frame_b_id
        assert len(restored.keypoints_a) == 1
        assert len(restored.matches) == 1
        assert restored.inlier_count == 1


class TestBundleAdjustmentResiduals:
    def test_improvement_factor(self):
        ba = BundleAdjustmentResiduals(
            stage_name="ba_stage",
            residuals_before=[2.0, 3.0, 4.0],
            residuals_after=[0.5, 0.6, 0.7],
        )
        assert ba.mean_before == pytest.approx(3.0)
        assert ba.mean_after == pytest.approx(0.6)
        assert ba.improvement_factor == pytest.approx(5.0)

    def test_improvement_factor_zero_after(self):
        ba = BundleAdjustmentResiduals(
            stage_name="ba_stage",
            residuals_before=[2.0],
            residuals_after=[0.0],
        )
        assert ba.improvement_factor == 0.0


class TestSeamDiagnostics:
    def test_frequency_profile_round_trip(self):
        fp = SeamFrequencyProfile(
            seam_id="seam_1",
            frequencies=[0.1, 0.2, 0.3],
            magnitudes_low=[1.0, 2.0, 3.0],
            magnitudes_high=[0.5, 1.0, 1.5],
            mismatch_score=0.25,
        )
        data = fp.to_dict()
        restored = SeamFrequencyProfile.from_dict(data)
        assert restored.seam_id == fp.seam_id
        assert restored.mismatch_score == fp.mismatch_score

    def test_gradient_coherence_mean(self):
        gc = SeamGradientCoherence(
            seam_id="seam_1",
            coherence=[0.1, 0.2, 0.3],
        )
        assert gc.mean_coherence == pytest.approx(0.2)

    def test_seam_diagnostic_round_trip(self):
        sd = SeamDiagnostic(
            seam_id="seam_1",
            source_frame_a="frame_001",
            source_frame_b="frame_002",
            routing_path=[(0.0, 0.0), (10.0, 10.0)],
            cut_energy=5.5,
        )
        data = sd.to_dict()
        restored = SeamDiagnostic.from_dict(data)
        assert restored.seam_id == sd.seam_id
        assert restored.cut_energy == sd.cut_energy


class TestStageDiagnosticReport:
    def test_empty_report_summary(self):
        report = StageDiagnosticReport(session_id="test_session")
        summary = report.to_dict()["summary"]
        assert summary["total_matches"] == 0
        assert summary["total_inliers"] == 0
        assert summary["mean_inlier_ratio"] == 0.0
        assert summary["ba_improvement"] == 0.0
        assert summary["mean_seam_coherence"] == 0.0

    def test_round_trip(self):
        report = StageDiagnosticReport(
            session_id="test_session",
            match_geometries=[
                MatchGeometry(
                    frame_a_id="a",
                    frame_b_id="b",
                    matches=[FeatureMatch(0, 0, 0.5, True)],
                    inlier_count=1,
                ),
            ],
            seam_diagnostics=[
                SeamDiagnostic(seam_id="seam_1", source_frame_a="a", source_frame_b="b"),
            ],
        )
        data = report.to_dict()
        restored = StageDiagnosticReport.from_dict(data)
        assert restored.session_id == report.session_id
        assert len(restored.match_geometries) == 1
        assert len(restored.seam_diagnostics) == 1


class TestTelemetryParsing:
    def test_parse_jsonl(self, tmp_path: Path):
        jsonl_path = tmp_path / "telemetry.jsonl"
        jsonl_path.write_text(
            '{"span": {"name": "test", "spanId": "abc", "traceId": "def", '
            '"startTimeUnixNano": 1000000000, "endTimeUnixNano": 2000000000, '
            '"attributes": {}, "status": {"code": 1}}}\n'
            '{"metric": {"name": "asp.stage.duration_ms", "gauge": {"asDouble": 42.0}, '
            '"unit": "ms", "attributes": {}}}\n'
        )

        envelopes = list(parse_telemetry_jsonl(jsonl_path))
        assert len(envelopes) == 2

        spans = extract_spans(envelopes)
        assert len(spans) == 1
        assert spans[0].name == "test"
        assert spans[0].duration_ms == 1000.0  # 1 second in ms

        metrics = extract_metrics(envelopes)
        assert len(metrics) == 1
        assert metrics[0].name == "asp.stage.duration_ms"
        assert metrics[0].value == 42.0

    def test_build_diagnostic_report(self, tmp_path: Path):
        jsonl_path = tmp_path / "telemetry.jsonl"
        jsonl_path.write_text(
            '{"metric": {"name": "asp.seam.cut_energy", "gauge": {"asDouble": 5.5}, '
            '"unit": "1", "attributes": {"asp.seam_id": "seam_1"}}}\n'
        )

        report = build_diagnostic_report("test_session", jsonl_path)
        assert report.session_id == "test_session"
        assert len(report.seam_diagnostics) == 1
        assert report.seam_diagnostics[0].seam_id == "seam_1"
        assert report.seam_diagnostics[0].cut_energy == 5.5


class TestCLI:
    def test_summarize_command(self, tmp_path: Path, capsys):
        jsonl_path = tmp_path / "telemetry.jsonl"
        jsonl_path.write_text(
            '{"metric": {"name": "asp.seam.cut_energy", "gauge": {"asDouble": 5.5}, '
            '"unit": "1", "attributes": {"asp.seam_id": "seam_1"}}}\n'
        )

        result = run_cli(["summarize", str(jsonl_path), "--session-id", "test"])
        assert result == 0

        captured = capsys.readouterr()
        assert "ASP CV Diagnostics Report: test" in captured.out
        assert "seam_1" in captured.out

    def test_list_telemetry_command(self, tmp_path: Path, capsys):
        (tmp_path / "telemetry1.jsonl").write_text("{}\n")
        (tmp_path / "telemetry2.jsonl").write_text("{}\n")

        result = run_cli(["list-telemetry", str(tmp_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "Found 2 telemetry file(s)" in captured.out

    def test_summarize_json_out(self, tmp_path: Path):
        jsonl_path = tmp_path / "telemetry.jsonl"
        jsonl_path.write_text("{}\n")
        json_out = tmp_path / "report.json"

        result = run_cli(["summarize", str(jsonl_path), "--json-out", str(json_out)])
        assert result == 0
        assert json_out.exists()

        report_data = json.loads(json_out.read_text())
        assert "session_id" in report_data
        assert "summary" in report_data


class TestDiscoverTelemetry:
    def test_discover_files(self, tmp_path: Path):
        (tmp_path / "a.jsonl").write_text("{}\n")
        (tmp_path / "b.jsonl").write_text("{}\n")
        (tmp_path / "c.txt").write_text("not jsonl\n")

        files = discover_telemetry_files(tmp_path)
        assert len(files) == 2
        assert all(f.suffix == ".jsonl" for f in files)

    def test_discover_empty_directory(self, tmp_path: Path):
        files = discover_telemetry_files(tmp_path)
        assert files == []

    def test_discover_nonexistent_directory(self):
        files = discover_telemetry_files("/nonexistent/path")
        assert files == []


class TestPluginManifest:
    def test_manifest_valid(self):
        manifest_path = Path(__file__).parent.parent.parent / "tool" / "plugins" / "asp_cv_diagnostics.plugin.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["schema"] == "devtool.plugin.manifest"
        assert manifest["name"] == "asp_cv_diagnostics"
        assert len(manifest["channels"]) == 3
        assert manifest["channels"][0]["key"] == "match_geometries"
        assert manifest["channels"][1]["key"] == "ba_residuals"
        assert manifest["channels"][2]["key"] == "seam_diagnostics"
