"""Enforce the Tauri webview security baseline (W0-04 / #868).

Four hard rules (fail CI, block merge):

1. ``app.security.csp`` in ``frontend/src-tauri/tauri.conf.json`` is a
   non-empty string — never ``null``.
2. Asset-protocol scopes are deny-by-default: no bare filesystem-root or
   home-dir wildcards (``**``, ``*``, ``/**``, ``$HOME/**``). The fixed
   prefix before any wildcard must name at least one directory level, so
   ``$HOME/.image-toolkit/cache/render/**`` passes and the old ``**``
   fails.
3. Every ``frontend/src-tauri/capabilities/*.json`` validates against the
   shipped capability schema pinned at
   ``frontend/src-tauri/schemas/desktop-schema.json`` (a committed copy of
   the ``gen/schemas`` file tauri-build generates — refresh it in the same
   PR that bumps the tauri version), and every permission identifier it
   grants exists in that schema.
4. Every capability window is a declared window label in
   ``tauri.conf.json``. Once ``migration/features.toml`` exists, every
   capability identifier must also appear in a ledger row; until the
   ledger lands (#882) the declared-window rule stands in for it.

Example:
    >>> python middleware/validation/check_tauri_security.py
    >>> python middleware/validation/check_tauri_security.py --root /path/to/repo
"""

import argparse
import fnmatch
import json
import sys
import tomllib
from pathlib import Path

TAURI_CONF_REL = Path("frontend/src-tauri/tauri.conf.json")
CAPABILITIES_REL = Path("frontend/src-tauri/capabilities")
SCHEMA_REL = Path("frontend/src-tauri/schemas/desktop-schema.json")
LEDGER_REL = Path("migration/features.toml")

# Wildcard scopes whose fixed prefix is a filesystem root, the home
# directory itself, or nothing at all.
ROOT_PREFIXES = frozenset({"", "/", "~", "$HOME"})


def _scope_is_root_wildcard(pattern: str) -> bool:
    """True when a scope pattern grants a whole root or the home dir."""
    text = pattern.strip()
    prefix = text.split("*", 1)[0].rstrip("/")
    return "*" in text and prefix in ROOT_PREFIXES


def _collect_permission_ids(schema: dict) -> set[str]:
    """All permission identifiers the shipped schema knows about."""
    identifiers: set[str] = set()
    for variant in schema["definitions"]["Identifier"].get("oneOf", []):
        if "const" in variant:
            identifiers.add(variant["const"])
        identifiers.update(variant.get("enum", []))
    return identifiers


def _capability_shape_violations(
    where: str,
    capability: dict,
    schema: dict,
) -> list[str]:
    """Top-level capability fields against the shipped schema shape."""
    violations: list[str] = []
    properties = set(schema["definitions"]["Capability"].get("properties", {}))
    required = set(schema["definitions"]["Capability"].get("required", {"identifier", "permissions"}))

    for key in capability:
        if key not in properties and key != "$schema":
            violations.append(f"{where}: unknown capability field '{key}'")
    for key in required:
        if key not in capability:
            violations.append(f"{where}: missing required field '{key}'")
    identifier = capability.get("identifier")
    if not isinstance(identifier, str) or not identifier:
        violations.append(f"{where}: 'identifier' must be a non-empty string")
    return violations


def _capability_window_violations(
    where: str,
    capability: dict,
    declared_windows: set[str],
    ledger_strings: set[str] | None,
) -> list[str]:
    violations: list[str] = []
    windows = capability.get("windows", [])
    if not isinstance(windows, list) or not all(isinstance(w, str) for w in windows):
        return [f"{where}: 'windows' must be a list of strings"]
    if not windows:
        violations.append(f"{where}: capability grants permissions to no window")
    for window in windows:
        if not any(fnmatch.fnmatchcase(label, window) for label in declared_windows):
            violations.append(
                f"{where}: window '{window}' is not declared in tauri.conf.json"
            )
        if ledger_strings is not None and window not in ledger_strings:
            violations.append(f"{where}: window '{window}' has no migration ledger row")
    if ledger_strings is not None and capability.get("identifier") not in ledger_strings:
        violations.append(
            f"{where}: capability '{capability.get('identifier')}' has no migration ledger row"
        )
    return violations


def _capability_permission_violations(
    where: str,
    capability: dict,
    permission_ids: set[str],
) -> list[str]:
    violations: list[str] = []
    permissions = capability.get("permissions")
    if not isinstance(permissions, list) or not permissions:
        return [f"{where}: 'permissions' must be a non-empty list"]

    for permission in permissions:
        permission_id = None
        if isinstance(permission, str):
            permission_id = permission
        elif isinstance(permission, dict) and isinstance(permission.get("identifier"), str):
            permission_id = permission["identifier"]
            for entry in permission.get("allow", []):
                path = entry.get("path") if isinstance(entry, dict) else None
                if isinstance(path, str) and _scope_is_root_wildcard(path):
                    violations.append(
                        f"{where}: permission '{permission_id}' grants a root-wildcard path '{path}'"
                    )
        else:
            violations.append(f"{where}: malformed permission entry {permission!r}")
            continue
        if permission_id not in permission_ids:
            violations.append(
                f"{where}: permission '{permission_id}' is not in the shipped capability schema"
            )
    return violations


def _capability_violations(
    path: Path,
    capability: dict,
    schema: dict,
    permission_ids: set[str],
    declared_windows: set[str],
    ledger_strings: set[str] | None,
) -> list[str]:
    violations = _capability_shape_violations(path.name, capability, schema)
    if "identifier" not in capability:
        return violations
    violations.extend(
        _capability_window_violations(path.name, capability, declared_windows, ledger_strings)
    )
    violations.extend(_capability_permission_violations(path.name, capability, permission_ids))
    return violations


def _ledger_leaves(node: object) -> set[str]:
    """Every string value in the migration ledger TOML tree."""
    found: set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            found |= _ledger_leaves(value)
    elif isinstance(node, list):
        for value in node:
            found |= _ledger_leaves(value)
    elif isinstance(node, str):
        found.add(node)
    return found


def _load_ledger_strings(root: Path) -> tuple[set[str] | None, list[str]]:
    """Ledger strings, or None with no violation while the ledger is absent."""
    ledger_path = root / LEDGER_REL
    if not ledger_path.exists():
        return None, []
    try:
        ledger = tomllib.loads(ledger_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return None, [f"{LEDGER_REL}: invalid TOML ({exc})"]
    return _ledger_leaves(ledger), []


def _conf_security_violations(conf: dict) -> list[str]:
    violations: list[str] = []
    security = conf.get("app", {}).get("security", {})

    csp = security.get("csp")
    if not isinstance(csp, str) or not csp.strip():
        violations.append(
            f"{TAURI_CONF_REL}: app.security.csp must be a non-empty string, got {csp!r}"
        )

    asset_protocol = security.get("assetProtocol", {})
    asset_scope = asset_protocol.get("scope", [])
    for pattern in asset_scope:
        if _scope_is_root_wildcard(pattern):
            violations.append(
                f"{TAURI_CONF_REL}: assetProtocol scope '{pattern}' is a root wildcard; "
                "declare feature roots instead"
            )
    if asset_protocol.get("enable") and not asset_scope:
        violations.append(f"{TAURI_CONF_REL}: assetProtocol is enabled with an empty scope")
    return violations


def check(root: Path) -> list[str]:
    conf_path = root / TAURI_CONF_REL
    try:
        conf = json.loads(conf_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"missing {TAURI_CONF_REL}"]
    except json.JSONDecodeError as exc:
        return [f"{TAURI_CONF_REL}: invalid JSON ({exc})"]

    violations = _conf_security_violations(conf)
    declared_windows = {
        window.get("label", "main")
        for window in conf.get("app", {}).get("windows", [])
    }

    schema_path = root / SCHEMA_REL
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return violations + [
            f"missing pinned capability schema {SCHEMA_REL} (see schemas/README.md)"
        ]
    except json.JSONDecodeError as exc:
        return violations + [f"{SCHEMA_REL}: invalid JSON ({exc})"]
    permission_ids = _collect_permission_ids(schema)

    ledger_strings, ledger_violations = _load_ledger_strings(root)
    violations.extend(ledger_violations)

    capability_dir = root / CAPABILITIES_REL
    if not capability_dir.is_dir():
        return violations + [f"missing {CAPABILITIES_REL}"]
    for path in sorted(capability_dir.glob("*.json")):
        try:
            capability = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(f"{path.name}: invalid JSON ({exc})")
            continue
        if not isinstance(capability, dict):
            violations.append(f"{path.name}: capability must be a JSON object")
            continue
        violations.extend(
            _capability_violations(
                path, capability, schema, permission_ids, declared_windows, ledger_strings
            )
        )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (default: auto-detect)",
    )
    args = parser.parse_args(argv)

    violations = check(args.root)
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        print(f"{len(violations)} violation(s).", file=sys.stderr)
        return 1
    print("PASS tauri security baseline (csp, asset scope, capabilities, schema)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
