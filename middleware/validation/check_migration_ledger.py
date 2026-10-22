"""Validate the migration ledger (W0-18 / #882).

``migration/features.toml`` holds one record per capability for the
PySide6 → Tauri migration (docs/moon/roadmaps/tauri_migration.md §2).
This check enforces:

1. Schema: every ``[[feature]]`` has the required keys with the right
   types; ``id`` unique; ``kind``/``status`` in their enums.
2. Catalog coherence (#869): page/workspace ids are catalog ids; window
   ids are not and own no routes.
3. Bidirectional route coverage: every catalog entry is owned by exactly
   one record; every ``routes`` id exists in the catalog.
4. Route-map completeness: every catalog alias and every owned entry's
   ``legacy_frontend_id`` appears in a ``route_map``; values are catalog
   ids.
5. Path existence: ``pyside``/``tauri``/``docs``/``scenarios`` entries
   exist (file, dir, or glob), except ``pyside`` of ``pyside-deleted``
   rows; non-empty ``service`` must exist and non-empty ``contract`` must
   be a capability in ``contracts/methods.toml``.
6. PySide ownership: every ``gui/src/**/*.py`` file is owned by exactly
   one ``pyside``/``[[shared]]`` entry.
7. Status gates: ``both``/``parity-passed`` need scenarios (unless there
   is no PySide6 surface to diff); ``parity-passed`` also needs docs and
   a fully checked ``os_checklist``.
8. ``[[exception]]`` records (consumed by check_migration_additive.py,
   #884): complete, referencing a real feature, never expired.
9. ``[shell].windows`` matches the catalog's window ids.

Example:
    >>> python middleware/validation/check_migration_ledger.py
    >>> python middleware/validation/check_migration_ledger.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any, Optional

LEDGER_REL = Path("migration/features.toml")
METHODS_REL = Path("contracts/methods.toml")
PYSIDE_ROOT = Path("gui/src")

KINDS = frozenset({"page", "workspace", "window"})
STATUSES = frozenset({"pyside-only", "both", "parity-passed", "pyside-deleted"})
PLATFORMS = frozenset({"linux", "windows", "macos"})

_FEATURE_SCHEMA: dict[str, tuple[type, ...]] = {
    "id": (str,),
    "kind": (str,),
    "title": (str,),
    "owner": (str,),
    "wave": (str,),
    "issue": (int,),
    "status": (str,),
    "routes": (list,),
    "route_map": (dict,),
    "pyside": (list,),
    "tauri": (list,),
    "service": (str,),
    "contract": (str,),
    "docs": (str,),
    "scenarios": (list,),
    "os_checklist": (list,),
}

_GLOB_CHARS = frozenset("*?[")


def _load_catalog() -> Any:
    """Import the #869 catalog, falling back to the repo root on sys.path."""
    try:
        from middleware.src.shell.catalog import shell_catalog
    except ImportError:
        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        from middleware.src.shell.catalog import shell_catalog
    return shell_catalog()


def _is_glob(pattern: str) -> bool:
    return any(char in _GLOB_CHARS for char in pattern)


def _resolve(root: Path, pattern: str) -> list[Path]:
    """Files/directories a ledger path entry points at (may be empty)."""
    target = root / pattern
    if target.exists():
        return [target]
    if _is_glob(pattern):
        return [match for match in root.glob(pattern)]
    return []


def _owned_py_files(root: Path, pattern: str) -> set[str]:
    """``gui/src``-relative ``.py`` files a pyside/shared entry owns."""
    owned: set[str] = []
    for match in _resolve(root, pattern):
        candidates = match.rglob("*.py") if match.is_dir() else iter([match])
        owned.extend(
            str(path.relative_to(root)) for path in candidates if path.suffix == ".py" and "__pycache__" not in path.parts
        )
    gui_prefix = f"{PYSIDE_ROOT}/"
    return {path for path in owned if path.startswith(gui_prefix)}


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _os_checklist_violations(where: str, checklist: Any) -> list[str]:
    violations: list[str] = []
    for item in checklist or []:
        if not isinstance(item, dict):
            violations.append(f"{where}: os_checklist entries must be tables")
            continue
        if not str(item.get("item", "")).strip():
            violations.append(f"{where}: os_checklist entry needs a non-empty 'item'")
        if item.get("platform") not in PLATFORMS:
            violations.append(f"{where}: os_checklist platform must be one of {sorted(PLATFORMS)}")
        if not isinstance(item.get("checked"), bool):
            violations.append(f"{where}: os_checklist 'checked' must be a bool")
    return violations


def _feature_violations(index: int, feature: Any, seen: set[str]) -> tuple[str, list[str]]:
    violations: list[str] = []
    where = f"[[feature]] #{index + 1}"
    if not isinstance(feature, dict):
        return where, [f"{where}: must be a table"]
    feature_id = feature.get("id", where)
    if isinstance(feature_id, str) and feature_id:
        where = f"feature {feature_id!r}"
        if feature_id in seen:
            violations.append(f"{where}: duplicate id")
        seen.add(feature_id)
    for key, types in _FEATURE_SCHEMA.items():
        value = feature.get(key)
        if value is None:
            violations.append(f"{where}: missing key {key!r}")
        elif not isinstance(value, types) or (isinstance(value, bool) and bool not in types):
            names = "/".join(t.__name__ for t in types)
            violations.append(f"{where}: key {key!r} must be {names}")
    for key in ("id", "kind", "title", "owner", "wave", "status"):
        if isinstance(feature.get(key), str) and not feature[key].strip():
            violations.append(f"{where}: key {key!r} must be non-empty")
    if isinstance(feature.get("kind"), str) and feature["kind"] not in KINDS:
        violations.append(f"{where}: kind {feature['kind']!r} not in {sorted(KINDS)}")
    if isinstance(feature.get("status"), str) and feature["status"] not in STATUSES:
        violations.append(f"{where}: status {feature['status']!r} not in {sorted(STATUSES)}")
    for key in ("routes", "pyside", "tauri", "scenarios"):
        if isinstance(feature.get(key), list) and not _string_list(feature[key]):
            violations.append(f"{where}: key {key!r} must be a list of strings")
    route_map = feature.get("route_map")
    if isinstance(route_map, dict) and not all(
        isinstance(old, str) and isinstance(new, str) for old, new in route_map.items()
    ):
        violations.append(f"{where}: 'route_map' must map strings to strings")
    violations.extend(_os_checklist_violations(where, feature.get("os_checklist")))
    return where, violations


def _schema_violations(features: list[Any]) -> list[str]:
    violations: list[str] = []
    seen: set[str] = set()
    for index, feature in enumerate(features):
        violations.extend(_feature_violations(index, feature, seen)[1])
    return violations


def _route_coverage_violations(features: list[dict], entries: dict[str, Any]) -> list[str]:
    """Bidirectional coverage: each catalog id owned by exactly one record."""
    violations: list[str] = []
    owner_of: dict[str, str] = {}
    for feature in features:
        feature_id = feature["id"]
        kind = feature["kind"]
        if kind in ("page", "workspace"):
            if feature_id not in entries:
                violations.append(f"feature {feature_id!r}: {kind} id is not in the #869 catalog")
        elif feature_id in entries:
            violations.append(f"feature {feature_id!r}: window id collides with a catalog id")
        if kind == "window" and feature["routes"]:
            violations.append(f"feature {feature_id!r}: window rows must have empty routes")
        owned = set(feature["routes"])
        if kind in ("page", "workspace"):
            owned.add(feature_id)
        if kind == "page" and set(feature["routes"]) != {feature_id}:
            violations.append(f"feature {feature_id!r}: a page row's routes must be [its own id]")
        for entry_id in sorted(owned):
            if entry_id not in entries:
                violations.append(f"feature {feature_id!r}: routes reference unknown catalog id {entry_id!r}")
                continue
            previous = owner_of.get(entry_id)
            if previous is not None:
                violations.append(f"catalog id {entry_id!r} is owned by both {previous!r} and {feature_id!r}")
            owner_of[entry_id] = feature_id
    for entry_id in sorted(entries):
        if entry_id not in owner_of:
            violations.append(f"catalog id {entry_id!r} is not owned by any feature row")
    return violations


def _route_map_violations(features: list[dict], catalog: Any, entries: dict[str, Any]) -> list[str]:
    """Aliases and legacy frontend ids must appear in a route_map."""
    violations: list[str] = []
    for alias in catalog.aliases:
        for feature in features:
            if feature["route_map"].get(alias.alias_id) == alias.target_id:
                break
        else:
            violations.append(
                f"catalog alias {alias.alias_id!r} -> {alias.target_id!r} is missing from every route_map"
            )
    for feature in features:
        for new in feature["route_map"].values():
            if new not in entries:
                violations.append(f"feature {feature['id']!r}: route_map value {new!r} is not a catalog id")
        owned = set(feature["routes"])
        if feature["kind"] in ("page", "workspace"):
            owned.add(feature["id"])
        for entry_id in sorted(owned):
            entry = entries.get(entry_id)
            if entry and entry.legacy_frontend_id and entry.legacy_frontend_id not in feature["route_map"]:
                violations.append(
                    f"feature {feature['id']!r}: route_map lacks legacy id {entry.legacy_frontend_id!r} "
                    f"for {entry_id!r}"
                )
    return violations


def _catalog_violations(features: list[dict], catalog: Any) -> list[str]:
    """Catalog coherence, route coverage, and route-map completeness."""
    entries = {entry.id: entry for entry in catalog.entries}
    return _route_coverage_violations(features, entries) + _route_map_violations(features, catalog, entries)


def _contract_capabilities(root: Path) -> set[str]:
    methods = root / METHODS_REL
    if not methods.is_file():
        return set()
    data = tomllib.loads(methods.read_text(encoding="utf-8"))
    return {str(method["capability"]) for method in data.get("method", []) if "capability" in method}


def _path_violations(root: Path, features: list[dict]) -> list[str]:
    violations: list[str] = []
    capabilities = _contract_capabilities(root)
    for feature in features:
        feature_id = feature["id"]
        path_keys = ["tauri", "scenarios"]
        if feature["status"] != "pyside-deleted":
            path_keys.append("pyside")
        for key in path_keys:
            for entry in feature[key]:
                if not _resolve(root, entry):
                    violations.append(f"feature {feature_id!r}: {key} path {entry!r} does not exist")
        service = feature["service"]
        if service and not (root / service).exists():
            violations.append(f"feature {feature_id!r}: service path {service!r} does not exist")
        docs = feature["docs"]
        if docs and not _resolve(root, docs):
            violations.append(f"feature {feature_id!r}: docs path {docs!r} does not exist")
        contract = feature["contract"]
        if contract and contract not in capabilities:
            violations.append(f"feature {feature_id!r}: contract {contract!r} is not a capability in {METHODS_REL}")
    return violations


def _ownership_violations(root: Path, features: list[dict], shared: list[Any]) -> list[str]:
    """Partition ``gui/src/**/*.py`` across feature pyside + shared entries."""
    violations: list[str] = []
    owner_of: dict[str, str] = {}
    claimants: list[tuple[str, str]] = []
    for feature in features:
        if feature["status"] == "pyside-deleted":
            continue  # deleted with the row's deletion PR
        claimants.extend((entry, f"feature {feature['id']!r}") for entry in feature["pyside"])
    for entry in shared:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            claimants.append((entry["path"], f"shared entry {entry['path']!r}"))
    for pattern, owner in claimants:
        for path in sorted(_owned_py_files(root, pattern)):
            previous = owner_of.get(path)
            if previous is not None:
                violations.append(f"{path} is owned by both {previous} and {owner}")
            owner_of[path] = owner
    gui_root = root / PYSIDE_ROOT
    if gui_root.is_dir():
        for path in sorted(gui_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = str(path.relative_to(root))
            if rel not in owner_of:
                violations.append(f"{rel} is not owned by any feature row or [[shared]] entry")
    return violations


def _status_violations(features: list[dict]) -> list[str]:
    violations: list[str] = []
    for feature in features:
        feature_id = feature["id"]
        status = feature["status"]
        if status in ("both", "parity-passed") and not feature["scenarios"] and feature["pyside"]:
            violations.append(
                f"feature {feature_id!r}: status {status!r} requires at least one parity scenario "
                "(only rows with no PySide6 surface are exempt)"
            )
        if status == "parity-passed":
            if not feature["docs"]:
                violations.append(f"feature {feature_id!r}: 'parity-passed' requires a docs path")
            unchecked = [item["item"] for item in feature["os_checklist"] if not item["checked"]]
            if unchecked:
                violations.append(
                    f"feature {feature_id!r}: 'parity-passed' requires a checked os_checklist; "
                    f"open: {', '.join(unchecked)}"
                )
    return violations


def _exception_violations(exceptions: list[Any], feature_ids: set[str]) -> list[str]:
    violations: list[str] = []
    for index, record in enumerate(exceptions):
        where = f"[[exception]] #{index + 1}"
        if not isinstance(record, dict):
            violations.append(f"{where}: must be a table")
            continue
        if isinstance(record.get("feature"), str) and record["feature"]:
            where = f"[[exception]] for {record['feature']!r}"
        missing = [key for key in ("feature", "path", "reason", "approved_by") if not str(record.get(key, "")).strip()]
        if missing:
            violations.append(f"{where}: missing or empty {', '.join(missing)}")
        issue = record.get("issue")
        if not isinstance(issue, int) or isinstance(issue, bool):
            violations.append(f"{where}: 'issue' must be an int")
        feature = record.get("feature")
        if isinstance(feature, str) and feature and feature not in feature_ids:
            violations.append(f"{where}: unknown feature {feature!r}")
        expires = record.get("expires")
        if expires is not None:
            try:
                expiry = expires if isinstance(expires, date) else date.fromisoformat(str(expires))
            except ValueError:
                violations.append(f"{where}: 'expires' is not an ISO date")
                continue
            if expiry < date.today():
                violations.append(f"{where}: expired {expiry}; remove the record instead of letting it rot")
    return violations


def _shell_violations(shell: Any, catalog: Any) -> list[str]:
    if not isinstance(shell, dict):
        return ["[shell] table is missing"]
    violations: list[str] = []
    windows = shell.get("windows")
    catalog_windows = sorted(window.id for window in catalog.windows)
    if not _string_list(windows or []):
        violations.append("[shell].windows must be a list of strings")
    elif sorted(windows) != catalog_windows:
        violations.append(f"[shell].windows {sorted(windows)} != catalog windows {catalog_windows}")
    capabilities = shell.get("capabilities")
    if not _string_list(capabilities or []) or not capabilities:
        violations.append("[shell].capabilities must be a non-empty list of strings")
    return violations


def check(root: Path, ledger_rel: Path = LEDGER_REL) -> list[str]:
    """All ledger violations under *root*, as human-readable strings."""
    ledger_path = root / ledger_rel
    if not ledger_path.is_file():
        return [f"missing {ledger_rel}"]
    try:
        data = tomllib.loads(ledger_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"{ledger_rel}: invalid TOML ({exc})"]

    catalog = _load_catalog()
    raw_features = data.get("feature", [])
    if not isinstance(raw_features, list):
        return [f"{ledger_rel}: [[feature]] must be an array of tables"]
    violations = _schema_violations(raw_features)
    features = [
        feature
        for feature in raw_features
        if isinstance(feature, dict)
        and all(isinstance(feature.get(key), types) for key, types in _FEATURE_SCHEMA.items())
    ]
    violations.extend(_catalog_violations(features, catalog))
    violations.extend(_path_violations(root, features))
    violations.extend(_ownership_violations(root, features, data.get("shared", [])))
    violations.extend(_status_violations(features))
    violations.extend(_exception_violations(data.get("exception", []), {f["id"] for f in features}))
    violations.extend(_shell_violations(data.get("shell"), catalog))
    return violations


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (default: auto-detect)",
    )
    parser.add_argument("--ledger", type=Path, default=LEDGER_REL, help="ledger path relative to root")
    args = parser.parse_args(argv)

    violations = check(args.root, args.ledger)
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        print(f"{len(violations)} violation(s).", file=sys.stderr)
        return 1
    print(f"PASS migration ledger ({args.root / args.ledger})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
