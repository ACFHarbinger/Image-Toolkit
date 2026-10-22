"""Unit tests for middleware/validation/check_migration_ledger.py and migration/generate_parity.py."""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from middleware.src.shell.catalog import CatalogKind, shell_catalog
from middleware.validation.check_migration_additive import load_ledger
from middleware.validation.check_migration_ledger import LEDGER_REL, check

REPO_ROOT = Path(__file__).resolve().parents[3]


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f'"{key}" = {_toml_value(item)}' for key, item in value.items()) + " }"
    raise TypeError(value)


def _valid_features():
    """One ledger row per catalog entry, mirroring the real ledger's shape."""
    catalog = shell_catalog()
    workspace_routes = {}
    for entry in catalog.entries:
        if entry.kind is CatalogKind.ROUTE:
            workspace_routes.setdefault(entry.workspace_id, []).append(entry.id)
    features = {}
    for entry in catalog.entries:
        if entry.kind is CatalogKind.ROUTE:
            continue
        kind = "page" if entry.kind is CatalogKind.PAGE else "workspace"
        features[entry.id] = {
            "id": entry.id,
            "kind": kind,
            "title": entry.title,
            "owner": "unclaimed",
            "wave": "wave-1",
            "issue": 1,
            "status": "pyside-only",
            "routes": [entry.id] if kind == "page" else sorted(workspace_routes[entry.id]),
            "route_map": ({entry.legacy_frontend_id: entry.id} if entry.legacy_frontend_id else {}),
            "pyside": [],
            "tauri": [],
            "service": "",
            "contract": "",
            "docs": "",
            "scenarios": [],
            "os_checklist": [],
        }
    for alias in catalog.aliases:
        owner = next(
            feature
            for feature in features.values()
            if alias.target_id in feature["routes"] or feature["id"] == alias.target_id
        )
        owner["route_map"][alias.alias_id] = alias.target_id
    return features


def _write_ledger(root: Path, features, shell=None, shared=(), exceptions=()):
    if shell is None:
        shell = {"windows": sorted(window.id for window in shell_catalog().windows), "capabilities": ["default"]}
    lines = ["[shell]"]
    lines += [f"{key} = {_toml_value(value)}" for key, value in shell.items()]
    for feature in features:
        lines.append("\n[[feature]]")
        lines += [f"{key} = {_toml_value(value)}" for key, value in feature.items()]
    for entry in shared:
        lines.append("\n[[shared]]")
        lines += [f"{key} = {_toml_value(value)}" for key, value in entry.items()]
    for record in exceptions:
        lines.append("\n[[exception]]")
        lines += [f"{key} = {_toml_value(value)}" for key, value in record.items()]
    ledger = root / LEDGER_REL
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ledger


def _check(root: Path):
    return check(root)


def test_valid_minimal_ledger_passes(tmp_path):
    _write_ledger(tmp_path, _valid_features().values())
    assert _check(tmp_path) == []


def test_duplicate_id_fails(tmp_path):
    features = list(_valid_features().values())
    features.append(dict(features[0]))
    _write_ledger(tmp_path, features)
    assert any("duplicate id" in violation for violation in _check(tmp_path))


def test_unowned_catalog_route_fails(tmp_path):
    features = _valid_features()
    stitch = features["stitch"]
    stitch["routes"] = [route for route in stitch["routes"] if route != "stitch.graph"]
    _write_ledger(tmp_path, features.values())
    assert any("'stitch.graph' is not owned" in violation for violation in _check(tmp_path))


def test_unknown_catalog_route_fails(tmp_path):
    features = _valid_features()
    features["system.convert"]["routes"] = ["system.convert", "system.bogus"]
    _write_ledger(tmp_path, features.values())
    assert any("unknown catalog id 'system.bogus'" in violation for violation in _check(tmp_path))


def test_missing_alias_in_route_map_fails(tmp_path):
    features = _valid_features()
    dl = features["dl"]
    dl["route_map"] = {old: new for old, new in dl["route_map"].items() if old != "ml.training"}
    _write_ledger(tmp_path, features.values())
    assert any("catalog alias 'ml.training'" in violation for violation in _check(tmp_path))


def test_missing_path_fails(tmp_path):
    features = _valid_features()
    features["system.convert"]["pyside"] = ["gui/src/tabs/core/convert_tab.py"]
    _write_ledger(tmp_path, features.values())
    assert any("does not exist" in violation for violation in _check(tmp_path))


def test_both_without_scenarios_fails(tmp_path):
    features = _valid_features()
    convert = features["system.convert"]
    convert["status"] = "both"
    convert["pyside"] = ["gui/src/tabs/core/convert_tab.py"]
    (tmp_path / "gui/src/tabs/core").mkdir(parents=True)
    (tmp_path / "gui/src/tabs/core/convert_tab.py").write_text("# stub\n", encoding="utf-8")
    _write_ledger(tmp_path, features.values(), shared=[{"path": "gui/src", "owner": "x", "note": "n"}])
    violations = _check(tmp_path)
    assert any("'both' requires at least one parity scenario" in violation for violation in violations)
    assert any("owned by both" in violation for violation in violations)


def test_frontend_only_row_may_skip_scenarios(tmp_path):
    features = _valid_features()
    benchmarks = features["developer.benchmarks"]
    benchmarks["status"] = "both"
    benchmarks["tauri"] = ["frontend/src/tabs/apollo"]
    (tmp_path / "frontend/src/tabs/apollo").mkdir(parents=True)
    _write_ledger(tmp_path, features.values())
    assert _check(tmp_path) == []


def test_parity_passed_with_unchecked_os_item_fails(tmp_path):
    features = _valid_features()
    wallpaper = features["system.wallpaper"]
    wallpaper["status"] = "parity-passed"
    wallpaper["docs"] = "docs/wallpaper.md"
    wallpaper["scenarios"] = ["middleware/test/parity/wallpaper.py"]
    wallpaper["os_checklist"] = [{"item": "per-monitor wallpaper", "platform": "linux", "checked": False}]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/wallpaper.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "middleware/test/parity").mkdir(parents=True)
    (tmp_path / "middleware/test/parity/wallpaper.py").write_text("# stub\n", encoding="utf-8")
    _write_ledger(tmp_path, features.values())
    assert any("checked os_checklist" in violation for violation in _check(tmp_path))


def test_expired_exception_fails(tmp_path):
    expired = (date.today() - timedelta(days=1)).isoformat()
    record = {
        "feature": "system.convert",
        "path": "middleware/migrations/005.py",
        "reason": "bounded destructive step",
        "issue": 884,
        "approved_by": "Harbinger",
        "expires": expired,
    }
    _write_ledger(tmp_path, _valid_features().values(), exceptions=[record])
    assert any("expired" in violation for violation in _check(tmp_path))


def test_exception_with_unknown_feature_fails(tmp_path):
    record = {
        "feature": "system.bogus",
        "path": "middleware/migrations/005.py",
        "reason": "bounded destructive step",
        "issue": 884,
        "approved_by": "Harbinger",
    }
    _write_ledger(tmp_path, _valid_features().values(), exceptions=[record])
    assert any("unknown feature 'system.bogus'" in violation for violation in _check(tmp_path))


def test_unknown_contract_capability_fails(tmp_path):
    features = _valid_features()
    features["system.convert"]["contract"] = "bogus"
    methods = tmp_path / "contracts/methods.toml"
    methods.parent.mkdir(parents=True)
    methods.write_text('[[method]]\nname = "system.ping"\ncapability = "system"\n', encoding="utf-8")
    _write_ledger(tmp_path, features.values())
    assert any("contract 'bogus' is not a capability" in violation for violation in _check(tmp_path))


def test_unowned_gui_file_fails(tmp_path):
    (tmp_path / "gui/src/tabs/core").mkdir(parents=True)
    (tmp_path / "gui/src/tabs/core/orphan.py").write_text("# stub\n", encoding="utf-8")
    _write_ledger(tmp_path, _valid_features().values())
    assert any("orphan.py is not owned" in violation for violation in _check(tmp_path))


def _run_generator(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "migration/generate_parity.py"), "--root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_generator_check_detects_drift_and_passes_when_fresh(tmp_path):
    _write_ledger(tmp_path, _valid_features().values())
    assert _run_generator(tmp_path, "--check").returncode == 1  # not generated yet
    assert _run_generator(tmp_path).returncode == 0
    assert _run_generator(tmp_path, "--check").returncode == 0
    doc = tmp_path / "docs/migration/parity.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
    result = _run_generator(tmp_path, "--check")
    assert result.returncode == 1
    assert "drift detected" in result.stdout


def test_real_repo_ledger_passes():
    assert check(REPO_ROOT) == []


def test_real_ledger_round_trips_through_additive_loader():
    _, _, errors = load_ledger(REPO_ROOT / LEDGER_REL)
    assert errors == []
