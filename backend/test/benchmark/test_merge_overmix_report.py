"""Unit tests for backend/benchmark/merge_overmix_report.py."""

import json
import tempfile
import pytest
from pathlib import Path
from backend.benchmark.merge_overmix_report import merge_overmix_results


def test_merge_overmix_results_empty_dir(tmp_path):
    res = merge_overmix_results(tmp_path)
    assert res["total_datasets"] == 0
    assert res["overmix_datasets_found"] == 0


def test_merge_overmix_results_with_artifacts(tmp_path):
    test1 = tmp_path / "test01"
    test1.mkdir()
    
    meta_path = test1 / "overmix_variant.json"
    meta_path.write_text(json.dumps({"aligner": "Recursive", "elapsed_sec": 1.2}), encoding="utf-8")

    img_path = test1 / "overmix_stitch.png"
    img_path.write_bytes(b"\x89PNG\r\n fake image bytes")

    output_json = tmp_path / "summary.json"
    res = merge_overmix_results(tmp_path, output_json)

    assert res["total_datasets"] == 1
    assert res["overmix_datasets_found"] == 1
    assert "test01" in res["datasets"]
    assert res["datasets"]["test01"]["overmix_present"] is True
    assert res["datasets"]["test01"]["overmix_img_exists"] is True
    assert output_json.exists()
