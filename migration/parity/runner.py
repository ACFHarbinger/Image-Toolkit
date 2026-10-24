"""Load a framework-neutral scenario and compare its two sides (#883).

A scenario file is JSON. ``kind`` is ``differential`` (legacy vs service on
one fixture) or ``characterization`` (service vs a stored oracle). The entry
is a Python file with ``pair(tmp)`` or ``current(tmp)``. It must not import a UI.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from migration.parity.diff import diff_values

_KINDS = frozenset({"differential", "characterization"})


@dataclass(frozen=True)
class Scenario:
    id: str
    feature: str
    kind: str
    entry: str
    oracle: str
    ignore: tuple[str, ...]
    path: Path


def load_scenario(path: Path) -> Scenario:
    """Read one scenario. Missing required fields raise ``ValueError``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    kind = str(data.get("kind", ""))
    if kind not in _KINDS:
        raise ValueError(f"{path} kind must be one of {sorted(_KINDS)}")
    entry = str(data.get("entry", ""))
    if not entry:
        raise ValueError(f"{path} needs an entry path")
    ignore = data.get("ignore", [])
    if not isinstance(ignore, list) or not all(isinstance(item, str) for item in ignore):
        raise ValueError(f"{path} ignore must be a list of strings")
    return Scenario(
        id=str(data.get("id", "")),
        feature=str(data.get("feature", "")),
        kind=kind,
        entry=entry,
        oracle=str(data.get("oracle", "")),
        ignore=tuple(ignore),
        path=path,
    )


def run_scenario(scenario: Scenario, tmp: Path, *, root: Path | None = None) -> list[str]:
    """Return the diff. Empty means the two sides agree."""
    base = root or _repo_root(scenario.path)
    module = _load(base / scenario.entry)
    if scenario.kind == "differential":
        left, right = module.pair(tmp)
        return diff_values(left, right, ignore=scenario.ignore)
    if not scenario.oracle:
        raise ValueError(f"{scenario.path} characterization needs an oracle")
    current = module.current(tmp)
    oracle = json.loads((base / scenario.oracle).read_text(encoding="utf-8"))
    return diff_values(current, oracle, ignore=scenario.ignore)


def _repo_root(scenario_path: Path) -> Path:
    for parent in scenario_path.resolve().parents:
        if (parent / "migration" / "features.toml").is_file():
            return parent
    raise ValueError(f"no repo root above {scenario_path}")


def _load(path: Path) -> ModuleType:
    if not path.is_file():
        raise ValueError(f"scenario entry does not exist: {path}")
    spec = importlib.util.spec_from_file_location(f"parity_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load scenario entry: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_match(scenario: Scenario, tmp: Path, *, root: Path | None = None) -> None:
    """Raise ``AssertionError`` with the mismatch list."""
    mismatches = run_scenario(scenario, tmp, root=root)
    if mismatches:
        joined = "\n".join(mismatches)
        raise AssertionError(f"{scenario.id} diverged:\n{joined}")


__all__ = ["Scenario", "assert_match", "diff_values", "load_scenario", "run_scenario"]
