"""Unit tests for middleware/validation/check_migration_additive.py."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

from middleware.validation.check_migration_additive import (
    ExceptionRecord,
    Violation,
    _allowed,
    added_lines,
    changed_migration_files,
    check_file_change,
    compare_schemas,
    load_ledger,
    scan_destructive,
)


def test_added_lines_ignores_context():
    before = "CREATE TABLE t (id INTEGER);\n-- keep\nSELECT 1;\n"
    after = "CREATE TABLE t (id INTEGER);\n-- keep\nSELECT 1;\nDROP TABLE t;\n"
    assert added_lines(before, after) == [(4, "DROP TABLE t;")]


def test_scan_destructive_flags_drop_and_rename_but_not_add():
    lines = [
        (1, "ALTER TABLE images ADD COLUMN caption TEXT;"),
        (2, "ALTER TABLE images DROP COLUMN caption;"),
        (3, "ALTER TABLE images RENAME TO pictures;"),
    ]
    violations = scan_destructive("middleware/migrations/005.py", lines)
    assert [violation.kind for violation in violations] == ["DROP", "RENAME"]


def test_compare_schemas_allows_additions():
    before = "CREATE TABLE t (id INTEGER, name TEXT);"
    after = "CREATE TABLE t (id INTEGER, name TEXT, note TEXT);\nCREATE TABLE u (id INTEGER);"
    assert compare_schemas("middleware/src/database/unified/schema.sql", before, after) == []


def test_compare_schemas_flags_removed_column_and_type_change():
    before = "CREATE TABLE t (id INTEGER, name TEXT, old TEXT);"
    after = "CREATE TABLE t (id TEXT, name TEXT);"
    details = [
        violation.detail for violation in compare_schemas("middleware/src/database/unified/schema.sql", before, after)
    ]
    assert any("column 'old' was removed" in detail for detail in details)
    assert any("column 'id' in table 't' changed" in detail for detail in details)


def test_check_file_change_checks_new_python_migration():
    violations = check_file_change(
        "middleware/migrations/005_drop_legacy.py",
        "",
        'db.execute("ALTER TABLE images DROP COLUMN legacy")\n',
    )
    assert len(violations) == 1
    assert violations[0].kind == "DROP"


def test_load_ledger_and_exception_matching(tmp_path: Path):
    ledger = tmp_path / "features.toml"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ledger.write_text(
        f'''
[[feature]]
id = "convert"
status = "pyside-deleted"
pyside = ["gui/src/tabs/system/convert"]

[[exception]]
feature = "convert"
path = "middleware/migrations/005*.py"
reason = "bounded fix"
issue = 884
approved_by = "Harbinger"
expires = "{tomorrow}"
''',
        encoding="utf-8",
    )
    deleted_paths, exceptions, errors = load_ledger(ledger)
    assert errors == []
    assert deleted_paths == ["gui/src/tabs/system/convert"]
    assert len(exceptions) == 1

    migrated = Violation("middleware/migrations/005_drop.py", 1, "DROP", "x")
    assert _allowed(migrated, deleted_paths, exceptions)
    assert _allowed(
        Violation("gui/src/tabs/system/convert/tab.py", 1, "DROP", "x"),
        deleted_paths,
        exceptions,
    )


def test_pyside_deleted_path_allows_without_exception():
    violation = Violation("gui/src/tabs/system/convert/tab.py", 1, "DROP", "x")
    assert _allowed(violation, ["gui/src/tabs/system/convert"], [])


def test_expired_exception_does_not_allow():
    yesterday = date.today() - timedelta(days=1)
    record = ExceptionRecord(
        feature="convert",
        path="middleware/migrations/005.py",
        reason="expired",
        issue="884",
        approved_by="Harbinger",
        expires=yesterday,
    )
    violation = Violation("middleware/migrations/005.py", 1, "DROP", "x")
    assert not _allowed(violation, [], [record])


def test_missing_ledger_has_no_exceptions(tmp_path: Path):
    deleted_paths, exceptions, errors = load_ledger(tmp_path / "features.toml")
    assert (deleted_paths, exceptions, errors) == ([], [], [])


def test_changed_migration_files_uses_base_and_head(tmp_path: Path):
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    migration = tmp_path / "middleware" / "migrations" / "001_init.py"
    migration.parent.mkdir(parents=True)
    migration.write_text("# init\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "init")

    new_migration = migration.parent / "002_add.py"
    new_migration.write_text("# add\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "add")

    assert changed_migration_files(tmp_path, "HEAD^", "HEAD") == ["middleware/migrations/002_add.py"]


def test_multiline_destructive_sql_is_rejected():
    result = check_file_change("middleware/migrations/005.py", "", 'db.execute("""DROP\nTABLE images""")')
    assert any(v.kind == "DROP" for v in result)


def test_deleted_schema_file_is_included_in_changed_files(tmp_path):
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    path = tmp_path / "middleware/src/cloud/store/schema.sql"
    path.parent.mkdir(parents=True)
    path.write_text("CREATE TABLE jobs (id TEXT);\n")
    git("add", ".")
    git("commit", "-qm", "schema")
    path.unlink()
    git("add", ".")
    git("commit", "-qm", "delete")
    assert changed_migration_files(tmp_path, "HEAD^", "HEAD") == ["middleware/src/cloud/store/schema.sql"]


def test_removing_a_table_constraint_is_not_additive():
    before = "CREATE TABLE jobs (id TEXT, UNIQUE (id));"
    after = "CREATE TABLE jobs (id TEXT);"
    result = compare_schemas("middleware/src/cloud/store/schema.sql", before, after)
    assert any("constraint" in v.detail for v in result)
