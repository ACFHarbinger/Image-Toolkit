"""Parity harness: diff, characterization, and the convert differential (#883)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from migration.parity.runner import assert_match, load_scenario, run_scenario

ROOT = Path(__file__).resolve().parents[3]
CONVERT = ROOT / "migration" / "scenarios" / "system.convert.json"


def test_diff_reports_a_changed_field(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text(
        "def pair(tmp):\n    return {'ok': True, 'size': 1}, {'ok': True, 'size': 2}\n",
        encoding="utf-8",
    )
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "sample",
                "feature": "system.convert",
                "kind": "differential",
                "entry": str(entry),
            }
        ),
        encoding="utf-8",
    )
    mismatches = run_scenario(load_scenario(scenario_path), tmp_path, root=tmp_path)
    assert mismatches == ["size: 1 != 2"]


def test_characterization_matches_a_stored_oracle(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text("def current(tmp):\n    return {'ok': True, 'elapsed': 9}\n", encoding="utf-8")
    oracle = tmp_path / "oracle.json"
    oracle.write_text(json.dumps({"ok": True, "elapsed": 1}), encoding="utf-8")
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "sample",
                "feature": "system.convert",
                "kind": "characterization",
                "entry": str(entry),
                "oracle": "oracle.json",
                "ignore": ["elapsed"],
            }
        ),
        encoding="utf-8",
    )
    assert run_scenario(load_scenario(scenario_path), tmp_path, root=tmp_path) == []


def _ensure_native_backend() -> None:
    """Use the built extension when a source tree named ``backend`` is on the path."""
    loaded = sys.modules.get("backend")
    if loaded is not None and hasattr(loaded, "convert_single_image"):
        return
    candidates: list[Path] = []
    roots = [Path(entry) for entry in sys.path if entry]
    # A worktree's ``backend/`` source tree can hide the extension built in the
    # checkout that owns this interpreter.
    roots.extend(Path(sys.prefix).resolve().parents)
    for root in roots:
        candidates.extend(root.glob("backend*.so"))
        if candidates:
            break
    if not candidates:
        pytest.skip("native backend extension is not built")
    spec = importlib.util.spec_from_file_location("backend", candidates[0])
    if spec is None or spec.loader is None:
        pytest.skip("native backend extension is not loadable")
    module = importlib.util.module_from_spec(spec)
    sys.modules["backend"] = module
    spec.loader.exec_module(module)


def test_convert_service_matches_the_canonical_converter(tmp_path: Path) -> None:
    _ensure_native_backend()
    scenario = load_scenario(CONVERT)
    assert scenario.feature == "system.convert"
    assert scenario.kind == "differential"
    assert_match(scenario, tmp_path, root=ROOT)


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"id": "x", "feature": "y", "kind": "pixel", "entry": "z"}), encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        load_scenario(path)
