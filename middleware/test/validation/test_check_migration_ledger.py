"""Unit tests for middleware/validation/check_migration_ledger.py."""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

from middleware.validation import check_migration_ledger as ledger_mod
from middleware.validation.check_migration_ledger import (
    _check_os_checklists,
    _check_ownership,
    _check_paths,
    _check_routes,
    _check_scenarios,
    parse_ledger,
    validate,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _catalog(ids, aliases=None, windows=("main",)):
    alias_rows = [
        SimpleNamespace(alias_id=old, target_id=new, applies_when=when)
        for when, mapping in (aliases or {}).items()
        for old, new in mapping.items()
    ]
    return SimpleNamespace(
        entries=[SimpleNamespace(id=entry_id) for entry_id in ids],
        aliases=alias_rows,
        windows=[SimpleNamespace(id=window_id) for window_id in windows],
        alias_map=lambda when: (aliases or {}).get(when, {}),
    )


def _feature(**overrides):
    base = dict(
        id="convert",
        title="Convert",
        issue=894,
        wave="1",
        owner="kimi",
        status="pyside-only",
        pyside=["gui/src/tabs/core/convert_tab.py"],
        pyside_exclude=[],
        tauri=[],
        service=None,
        contract=None,
        docs=[],
        scenarios=["convert-single-format"],
        windows=["main"],
        capabilities=[],
        routes=[ledger_mod.Route(old="convert", to="system.convert", alias=None)],
        os_checklist=[
            ledger_mod.OsEntry(os=name, status="pending", notes="")
            for name in ("linux", "windows", "macos")
        ],
        notes="",
    )
    base.update(overrides)
    return ledger_mod.Feature(**base)


def _write_ledger(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "migration" / "features.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


MINIMAL_LEDGER = """
[ledger]
version = 1
contracts_hash = "abc123"

[[feature]]
id = "convert"
title = "Convert"
issue = 894
wave = "1"
owner = "kimi"
status = "pyside-only"
pyside = ["gui/src/tabs/core/convert_tab.py"]
scenarios = ["convert-single-format"]
windows = ["main"]

[[feature.routes]]
from = "convert"
to = "system.convert"

[[feature.os_checklist]]
os = "linux"
status = "pending"
[[feature.os_checklist]]
os = "windows"
status = "pending"
[[feature.os_checklist]]
os = "macos"
status = "pending"
"""


def test_parse_minimal_ledger(tmp_path: Path):
    path = _write_ledger(tmp_path, MINIMAL_LEDGER)
    ledger = parse_ledger(tomllib.loads(path.read_text(encoding="utf-8")))
    assert ledger.errors == []
    (feature,) = ledger.features
    assert feature.id == "convert"
    assert feature.routes == [ledger_mod.Route(old="convert", to="system.convert", alias=None)]
    assert [entry.os for entry in feature.os_checklist] == ["linux", "windows", "macos"]


def test_parse_flags_missing_fields_and_unknown_keys(tmp_path: Path):
    body = MINIMAL_LEDGER.replace('title = "Convert"\n', "").replace(
        'status = "pyside-only"', 'status = "gone"\nowned_by = "nobody"'
    )
    path = _write_ledger(tmp_path, body)
    ledger = parse_ledger(tomllib.loads(path.read_text(encoding="utf-8")))
    assert any("missing title" in error for error in ledger.errors)
    assert any("unknown status 'gone'" in error for error in ledger.errors)
    assert any("unknown field 'owned_by'" in error for error in ledger.errors)


def test_parse_flags_duplicate_ids_and_bad_scenarios(tmp_path: Path):
    body = MINIMAL_LEDGER + "\n[[feature]]\n" + MINIMAL_LEDGER.split("[[feature]]\n", 1)[1].replace(
        "convert-single-format", "Convert Single"
    )
    path = _write_ledger(tmp_path, body)
    ledger = parse_ledger(tomllib.loads(path.read_text(encoding="utf-8")))
    assert any("duplicated" in error for error in ledger.errors)
    assert any("'Convert Single' must be kebab-case" in error for error in _check_scenarios(ledger.features))


def test_route_coverage_both_ways():
    ids = {"system.convert", "system.merge"}
    features = [_feature()]
    errors = _check_routes(ids, {}, features)
    assert errors == ["catalog id 'system.merge' is not covered by any ledger row"]

    features[0].routes.append(ledger_mod.Route(old=None, to="elsewhere", alias=None))
    errors = _check_routes(ids, {}, features)
    assert any("'elsewhere' is not a catalog id" in error for error in errors)


def test_route_double_claim_and_alias_matching():
    ids = {"ml.training", "dl.train", "dl.review"}
    aliases = {"experimental-dl": {"ml.training": "dl.train"}}
    bad = _feature(
        routes=[
            ledger_mod.Route(old="train", to="ml.training", alias=None),
            ledger_mod.Route(old="train", to="ml.training", alias=None),
            ledger_mod.Route(old="ml.training", to="dl.review", alias="experimental-dl"),
        ]
    )
    errors = _check_routes(ids, aliases, [bad])
    assert any("'ml.training' is claimed by both" in error for error in errors)
    assert any("old route 'train' is mapped by both" in error for error in errors)
    assert any("does not match the catalog's 'experimental-dl' alias map" in error for error in errors)

    good = _feature(
        routes=[
            ledger_mod.Route(old="train", to="ml.training", alias=None),
            ledger_mod.Route(old="ml.training", to="dl.train", alias="experimental-dl"),
            ledger_mod.Route(old=None, to="dl.review", alias=None),
        ]
    )
    assert _check_routes(ids, aliases, [good]) == []


def test_alias_rows_may_share_a_target():
    ids = {"ml.evaluation", "ml.inference", "dl.review"}
    aliases = {"experimental-dl": {"ml.evaluation": "dl.review", "ml.inference": "dl.review"}}
    feature = _feature(
        routes=[
            ledger_mod.Route(old="evaluate", to="ml.evaluation", alias=None),
            ledger_mod.Route(old="inference", to="ml.inference", alias=None),
            ledger_mod.Route(old="ml.evaluation", to="dl.review", alias="experimental-dl"),
            ledger_mod.Route(old="ml.inference", to="dl.review", alias="experimental-dl"),
        ]
    )
    assert _check_routes(ids, aliases, [feature]) == []


def test_plain_route_from_cannot_be_a_catalog_id():
    ids = {"system.convert", "dl.train"}
    feature = _feature(
        routes=[
            ledger_mod.Route(old="convert", to="system.convert", alias=None),
            ledger_mod.Route(old="system.convert", to="dl.train", alias=None),
        ]
    )
    errors = _check_routes(ids, {}, [feature])
    assert any("record the alias condition" in error for error in errors)


def test_paths_exist_for_live_rows_and_are_gone_for_deleted(tmp_path: Path):
    (tmp_path / "gui/src/tabs/core").mkdir(parents=True)
    (tmp_path / "gui/src/tabs/core/convert_tab.py").touch()
    live = _feature()
    assert _check_paths(tmp_path, [live]) == []

    deleted = _feature(status="pyside-deleted")
    errors = _check_paths(tmp_path, [deleted])
    assert any("still exists but the row is pyside-deleted" in error for error in errors)

    missing = _feature(pyside=["gui/src/tabs/core/nope.py"])
    errors = _check_paths(tmp_path, [missing])
    assert any("'gui/src/tabs/core/nope.py' does not exist" in error for error in errors)


def test_exclude_must_live_under_own_paths_and_capabilities_exist(tmp_path: Path):
    (tmp_path / "gui/src/tabs/core").mkdir(parents=True)
    (tmp_path / "gui/src/tabs/core/convert_tab.py").touch()
    (tmp_path / "frontend/src-tauri/capabilities").mkdir(parents=True)
    bad = _feature(
        pyside=["gui/src/tabs/core/convert_tab.py", "gui/src/tabs"],
        pyside_exclude=["gui/src/windows"],
        capabilities=["default"],
    )
    errors = _check_paths(tmp_path, [bad])
    assert any("pyside_exclude 'gui/src/windows' is not under" in error for error in errors)
    assert any("capability 'default' has no file" in error for error in errors)


def test_ownership_requires_exactly_one_row(tmp_path: Path):
    gui_src = tmp_path / "gui/src"
    (gui_src / "tabs/core").mkdir(parents=True)
    (gui_src / "tabs/core/convert_tab.py").touch()
    (gui_src / "tabs/core/merge_tab.py").touch()
    (gui_src / "components").mkdir()
    (gui_src / "components/kit.py").touch()

    convert = _feature(pyside=["gui/src/tabs/core/convert_tab.py"])
    shared = _feature(id="shared-qt-infrastructure", pyside=["gui/src/components"])
    errors = _check_ownership(tmp_path, [convert, shared])
    assert errors == ["gui/src/tabs/core/merge_tab.py: no ledger row owns this PySide6 file"]

    greedy = _feature(id="shell", pyside=["gui/src"])
    errors = _check_ownership(tmp_path, [convert, shared, greedy])
    assert any("owned by multiple rows" in error for error in errors)

    excluded = _feature(
        id="shell",
        pyside=["gui/src/tabs"],
        pyside_exclude=["gui/src/tabs/core/convert_tab.py"],
    )
    assert _check_ownership(tmp_path, [convert, shared, excluded]) == []


def test_ownership_ignores_bytecode_next_to_owned_sources(tmp_path: Path):
    gui_src = tmp_path / "gui/src/tabs"
    gui_src.mkdir(parents=True)
    (gui_src / "convert_tab.py").touch()
    (gui_src / "convert_tab.pyc").write_bytes(b"pyc")
    cache = gui_src / "__pycache__"
    cache.mkdir()
    (cache / "convert_tab.cpython-311.pyc").write_bytes(b"pyc")
    owner = _feature(pyside=["gui/src/tabs/convert_tab.py"])
    assert _check_ownership(tmp_path, [owner]) == []


def test_deleted_rows_do_not_participate_in_ownership(tmp_path: Path):
    gui_src = tmp_path / "gui/src"
    (gui_src / "tabs").mkdir(parents=True)
    (gui_src / "tabs/old.py").touch()
    owner = _feature(pyside=["gui/src/tabs"])
    ghost = _feature(id="retired", status="pyside-deleted", pyside=["gui/src/gone"])
    assert _check_ownership(tmp_path, [owner, ghost]) == []


def test_scenarios_present_and_unique():
    first = _feature()
    second = _feature(id="merge", scenarios=["convert-single-format"])
    errors = _check_scenarios([first, second])
    assert any("declared by both" in error for error in errors)
    third = _feature(id="empty", scenarios=[])
    assert any("at least one scenario is required" in error for error in _check_scenarios([third]))


def test_os_checklist_gate_on_deletion():
    feature = _feature()
    assert _check_os_checklists([feature]) == []

    deleted = _feature(status="pyside-deleted")
    assert any("passed/na" in error for error in _check_os_checklists([deleted]))

    deleted.os_checklist = [
        ledger_mod.OsEntry(os=name, status="passed", notes="") for name in ("linux", "windows", "macos")
    ]
    assert _check_os_checklists([deleted]) == []

    short = _feature(os_checklist=[ledger_mod.OsEntry(os="linux", status="pending", notes="")])
    assert any("must cover exactly" in error for error in _check_os_checklists([short]))


def test_shipped_ledger_is_valid():
    """The committed ledger must pass every rule against the real tree."""
    assert validate(REPO_ROOT) == []
