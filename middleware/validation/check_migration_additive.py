"""Enforce additive-only schema migrations while a PySide6 row lives (W0-20).

Kimi Q7 (Harbinger answer A): a migration touching a live Qt row's tables
must add, not rename/drop; destructive steps ride with the row's deletion
PR. This check runs on the files a branch changed, not the whole tree, so
pre-existing legacy drops are not re-litigated.

Rules:

1. Added SQL in a changed migration/schema file must not contain
   ``DROP TABLE|COLUMN|INDEX|VIEW|TRIGGER|CONSTRAINT``,
   ``RENAME TO|COLUMN``, ``ALTER COLUMN ... TYPE`` or ``TRUNCATE``.
2. A changed schema definition (``schema*.sql``) must not remove a table
   or a column, or change an existing column's definition.
3. A destructive step inside a ``pyside-deleted`` feature's own
   ``pyside`` paths is allowed (the row's deletion PR); anything else
   needs a matching, unexpired ``[[exception]]`` record.

Exceptions are records in the migration ledger (#882); this check does not
create a second ledger.

Example:
    >>> python middleware/validation/check_migration_additive.py
    >>> python middleware/validation/check_migration_additive.py --base origin/main
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

MIGRATION_PATHS = (
    "middleware/migrations",
    "middleware/src/database",
    "middleware/src/cloud/store",
    "frontend/src-tauri/migrations",
)

MIGRATION_GLOBS = (
    "middleware/migrations/*.py",
    "middleware/src/database/*.py",
    "middleware/src/database/**/*.py",
    "middleware/src/database/*.sql",
    "middleware/src/database/**/*.sql",
    "middleware/src/cloud/store/*.py",
    "middleware/src/cloud/store/*.sql",
    "frontend/src-tauri/migrations/*.sql",
)

SCHEMA_GLOBS = (
    "middleware/src/database/**/schema*.sql",
    "middleware/src/cloud/store/schema*.sql",
)

LEDGER_PATH = Path("migration/features.toml")

_DESTRUCTIVE = (
    (
        "DROP",
        re.compile(r"\bDROP\s+(?:TABLE|COLUMN|INDEX|VIEW|TRIGGER|CONSTRAINT)\b", re.IGNORECASE),
    ),
    ("RENAME", re.compile(r"\bRENAME\s+(?:TO|COLUMN)\b", re.IGNORECASE)),
    (
        "ALTER COLUMN TYPE",
        re.compile(r"\bALTER\s+COLUMN\s+[\w\"`\[\].]+\s+(?:SET\s+DATA\s+)?TYPE\b", re.IGNORECASE),
    ),
    ("TRUNCATE", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
)

_TABLE_CONSTRAINTS = frozenset({"primary", "unique", "check", "foreign", "constraint"})
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\"`.\[\]]+)\s*\(",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    """One non-additive change that needs a ledger exception."""

    path: str
    line: Optional[int]
    kind: str
    detail: str

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.kind}: {self.detail}"


@dataclass(frozen=True)
class Column:
    line: int
    definition: str


@dataclass(frozen=True)
class Table:
    line: int
    columns: dict[str, Column]


@dataclass(frozen=True)
class ExceptionRecord:
    feature: str
    path: str
    reason: str
    issue: str
    approved_by: str
    expires: Optional[date]


def _line_at(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _split_top_level(body: str) -> list[tuple[int, str]]:
    parts: list[tuple[int, str]] = []
    depth = 0
    start = 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append((start, body[start:index]))
            start = index + 1
    parts.append((start, body[start:]))
    return parts


def _parse_columns(source: str, body_start: int, body: str) -> dict[str, Column]:
    columns: dict[str, Column] = {}
    for offset, part in _split_top_level(body):
        stripped = part.strip()
        if not stripped:
            continue
        head = stripped.split(None, 1)
        name = head[0].strip('"`[]')
        if name.lower() in _TABLE_CONSTRAINTS:
            continue
        definition = re.sub(r"\s+", " ", head[1] if len(head) > 1 else "").strip()
        leading = len(part) - len(part.lstrip())
        columns[name.lower()] = Column(
            line=_line_at(source, body_start + offset + leading),
            definition=definition,
        )
    return columns


def parse_create_tables(sql: str) -> dict[str, Table]:
    """Return ``{table: Table}`` for the plain ``CREATE TABLE`` statements."""
    source = _strip_sql_comments(sql)
    tables: dict[str, Table] = {}
    for match in _CREATE_TABLE.finditer(source):
        start = match.end()
        depth = 1
        index = start
        while index < len(source) and depth:
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
            index += 1
        body = source[start : index - 1]
        tables[match.group(1).strip('"`[]').lower()] = Table(
            line=_line_at(source, match.start()),
            columns=_parse_columns(source, start, body),
        )
    return tables


def added_lines(before: str, after: str) -> list[tuple[int, str]]:
    """Return ``(line_number, text)`` for lines inserted or replaced in *after*."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    result: list[tuple[int, str]] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            result.extend((line_no, after_lines[line_no - 1]) for line_no in range(j1 + 1, j2 + 1))
    return result


def scan_destructive(path: str, lines: Iterable[tuple[int, str]]) -> list[Violation]:
    violations: list[Violation] = []
    for line_no, text in lines:
        for kind, pattern in _DESTRUCTIVE:
            if pattern.search(text):
                violations.append(
                    Violation(
                        path=path,
                        line=line_no,
                        kind=kind,
                        detail="destructive DDL is not additive; move it to the row's deletion PR "
                        "or record a bounded [[exception]] in migration/features.toml",
                    )
                )
    return violations


def compare_schemas(path: str, before: str, after: str) -> list[Violation]:
    """Flag removed/changed tables and columns between two schema definitions."""
    previous = parse_create_tables(before)
    current = parse_create_tables(after)
    violations: list[Violation] = []

    for name, table in previous.items():
        replacement = current.get(name)
        if replacement is None:
            violations.append(
                Violation(
                    path=path,
                    line=None,
                    kind="SCHEMA",
                    detail=f"table {name!r} was removed or renamed; deletion belongs in the row's deletion PR",
                )
            )
            continue
        for column_name, column in table.columns.items():
            replacement_column = replacement.columns.get(column_name)
            if replacement_column is None:
                violations.append(
                    Violation(
                        path=path,
                        line=replacement.line,
                        kind="SCHEMA",
                        detail=f"column {column_name!r} was removed from table {name!r}",
                    )
                )
            elif replacement_column.definition != column.definition:
                violations.append(
                    Violation(
                        path=path,
                        line=replacement_column.line,
                        kind="SCHEMA",
                        detail=(
                            f"column {column_name!r} in table {name!r} changed from "
                            f"{column.definition!r} to {replacement_column.definition!r}"
                        ),
                    )
                )
    return violations


def _is_schema_file(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in SCHEMA_GLOBS)


def check_file_change(path: str, before: str, after: str) -> list[Violation]:
    """Apply the additive rules to one changed migration/schema file."""
    violations = scan_destructive(path, added_lines(before, after))
    if _is_schema_file(path):
        violations.extend(compare_schemas(path, before, after))
    return violations


def load_ledger(path: Path) -> tuple[list[str], list[ExceptionRecord], list[str]]:
    """Read paths owned by deleted features and validated ``[[exception]]`` records."""
    if not path.is_file():
        return [], [], []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [], [], [f"{path}: cannot read the migration ledger: {exc}"]

    deleted_paths: list[str] = []
    for feature in data.get("feature", []):
        if not isinstance(feature, dict) or feature.get("status") != "pyside-deleted":
            continue
        deleted_paths.extend(str(item) for item in feature.get("pyside", []) if str(item).strip())

    exceptions: list[ExceptionRecord] = []
    errors: list[str] = []
    for raw in data.get("exception", []):
        if not isinstance(raw, dict):
            errors.append(f"{path}: every [[exception]] must be a table")
            continue
        missing = [
            key for key in ("feature", "path", "reason", "issue", "approved_by") if not str(raw.get(key, "")).strip()
        ]
        if missing:
            errors.append(f"{path}: [[exception]] missing {', '.join(missing)}")
            continue
        expires = None
        if raw.get("expires"):
            try:
                expires = date.fromisoformat(str(raw["expires"]))
            except ValueError:
                errors.append(f"{path}: [[exception]] has an invalid expires date")
                continue
        exceptions.append(
            ExceptionRecord(
                feature=str(raw["feature"]),
                path=str(raw["path"]),
                reason=str(raw["reason"]),
                issue=str(raw["issue"]),
                approved_by=str(raw["approved_by"]),
                expires=expires,
            )
        )
    return deleted_paths, exceptions, errors


def _path_matches(path: str, pattern: str) -> bool:
    normalized = pattern.rstrip("/")
    return path == normalized or path.startswith(f"{normalized}/") or fnmatch.fnmatch(path, pattern)


def _allowed(violation: Violation, deleted_paths: list[str], exceptions: list[ExceptionRecord]) -> bool:
    if any(_path_matches(violation.path, path) for path in deleted_paths):
        return True
    for record in exceptions:
        if not _path_matches(violation.path, record.path):
            continue
        if record.expires is not None and record.expires < date.today():
            continue
        return True
    return False


def _run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def _git_show(root: Path, ref: str, path: str) -> str:
    try:
        return _run_git(root, "show", f"{ref}:{path}")
    except RuntimeError:
        return ""


def _content(root: Path, ref: Optional[str], path: str) -> str:
    if ref is None:
        target = root / path
        return target.read_text(encoding="utf-8") if target.is_file() else ""
    return _git_show(root, ref, path)


def changed_migration_files(root: Path, base: str, head: Optional[str]) -> list[str]:
    revision = f"{base}...{head}" if head else base
    output = _run_git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        revision,
        "--",
        *MIGRATION_PATHS,
    )
    return sorted(
        path for path in output.splitlines() if any(fnmatch.fnmatch(path, pattern) for pattern in MIGRATION_GLOBS)
    )


def _resolve_base() -> str:
    if os.environ.get("GITHUB_BASE_REF"):
        return f"origin/{os.environ['GITHUB_BASE_REF']}"
    return "HEAD^"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--base", default=None, help="Git ref to compare from (default: origin/<GITHUB_BASE_REF> or HEAD^)"
    )
    parser.add_argument("--head", default=None, help="Git ref to compare to (default: working tree)")
    parser.add_argument("--ledger", default=str(LEDGER_PATH), help="Migration ledger path")
    args = parser.parse_args()

    root = Path(args.root)
    ledger = root / args.ledger
    deleted_paths, exceptions, ledger_errors = load_ledger(ledger)
    base = args.base or _resolve_base()
    target = args.head or "the working tree"

    try:
        changed = changed_migration_files(root, base, args.head)
    except RuntimeError as exc:
        print(f"migration guard: cannot diff {base}...{target}: {exc}", file=sys.stderr)
        return 2

    violations: list[Violation] = []
    for path in changed:
        before = _git_show(root, base, path)
        after = _content(root, args.head, path)
        violations.extend(check_file_change(path, before, after))

    violations = [violation for violation in violations if not _allowed(violation, deleted_paths, exceptions)]

    if violations:
        for error in ledger_errors:
            print(error)
        for violation in violations:
            print(violation)
        print(f"{len(violations) + len(ledger_errors)} migration-guard violation(s); see issue #884.")
        return 1
    if ledger_errors:
        # The ledger belongs to #882's validator; warn here instead of
        # duplicating its schema checks when there is nothing to suppress.
        for error in ledger_errors:
            print(f"warning: {error}")
    print(f"migration guard OK: {len(changed)} changed migration file(s), all additive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
