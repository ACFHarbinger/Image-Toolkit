"""Structural diff for parity scenarios (#883).

The comparison is JSON-shaped data. UI frameworks stay outside this module.
"""

from __future__ import annotations

from typing import Any


def diff_values(left: Any, right: Any, *, ignore: tuple[str, ...] = ()) -> list[str]:
    """Return human-readable mismatches. An empty list means the values agree."""
    skipped = set(ignore)
    return _walk(left, right, "", skipped)


def _walk(left: Any, right: Any, path: str, ignore: set[str]) -> list[str]:
    if path in ignore or (path and path.split(".")[-1] in ignore):
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        mismatches: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                mismatches.append(f"{child}: present on only one side")
                continue
            mismatches.extend(_walk(left[key], right[key], child, ignore))
        return mismatches
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{path or '<root>'}: length {len(left)} != {len(right)}"]
        mismatches = []
        for index, (item, other) in enumerate(zip(left, right, strict=True)):
            mismatches.extend(_walk(item, other, f"{path}[{index}]", ignore))
        return mismatches
    if left != right:
        return [f"{path or '<root>'}: {left!r} != {right!r}"]
    return []
