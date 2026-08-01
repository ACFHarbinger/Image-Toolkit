"""Tests for BrowserRepo (backend/src/database/unified/browser_repo.py) —
DB.9's Data Browser tab backend.

Engine-level tests over a tmp SQLCipher database; no GUI, no JVM.
"""

import pytest

base = pytest.importorskip("base")

from backend.src.database.unified import session  # noqa: E402
from backend.src.database.unified.browser_repo import BrowserRepo  # noqa: E402
from backend.src.database.unified.image_repo import ImageRepo  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    handle = base.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    session.ensure_schema(handle)
    yield handle
    handle.close()


def test_list_tables_includes_known_excludes_internal(db):
    repo = BrowserRepo(db)
    tables = repo.list_tables()
    assert "images" in tables
    assert "media_items" in tables
    assert "tags" in tables
    assert not any(t.startswith("sqlite_") for t in tables)


def test_table_columns_shape(db):
    repo = BrowserRepo(db)
    cols = repo.table_columns("images")
    names = {c["name"] for c in cols}
    assert {"id", "file_path", "phash"} <= names
    pk_col = next(c for c in cols if c["name"] == "id")
    assert pk_col["pk"] is True
    non_pk = next(c for c in cols if c["name"] == "file_path")
    assert non_pk["pk"] is False


def test_table_columns_unknown_table_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown table"):
        repo.table_columns("not_a_real_table")


def test_table_row_count(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    assert repo.table_row_count("images") == 0
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        images.add_image(str(p), tags=[])
    assert repo.table_row_count("images") == 2


def test_query_table_pagination_and_where(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    ids = {}
    for name in ("a.png", "b.png", "c.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        ids[name] = images.add_image(str(p), tags=[])

    columns, rows = repo.query_table("images", limit=2, offset=0)
    assert "file_path" in columns
    assert len(rows) == 2

    columns, rows = repo.query_table("images", limit=2, offset=2)
    assert len(rows) == 1

    file_path_idx = columns.index("file_path")
    columns, rows = repo.query_table(
        "images", where_sql="filename = 'b.png'", limit=100, offset=0
    )
    assert len(rows) == 1
    assert rows[0][file_path_idx].endswith("b.png")


def test_query_table_unknown_table_rejected(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown table"):
        repo.query_table("not_a_real_table")


def test_table_foreign_keys(db):
    repo = BrowserRepo(db)
    fks = repo.table_foreign_keys("images")
    by_column = {fk["column"]: fk for fk in fks}
    assert by_column["group_id"] == {
        "column": "group_id", "ref_table": "groups", "ref_column": "id",
    }
    assert by_column["subgroup_id"] == {
        "column": "subgroup_id", "ref_table": "subgroups", "ref_column": "id",
    }

    # A table with no FKs returns an empty list, not an error.
    assert repo.table_foreign_keys("groups") == []


def test_table_foreign_keys_unknown_table_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown table"):
        repo.table_foreign_keys("not_a_real_table")


def test_reverse_references(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    gid = images.add_group("Trips")

    # Nothing references the group yet.
    assert repo.reverse_references("groups", gid) == []

    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        images.add_image(str(p), group_name="Trips", tags=[])
    images.add_subgroup("Beach", "Trips")

    refs = {(r["table"], r["column"]): r["count"] for r in repo.reverse_references("groups", gid)}
    assert refs[("images", "group_id")] == 2
    assert refs[("subgroups", "group_id")] == 1

    # A group with no rows referencing it is simply absent (no zero-count
    # noise in the panel).
    other_gid = images.add_group("Empty")
    assert repo.reverse_references("groups", other_gid) == []


def test_reverse_references_unknown_table_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown table"):
        repo.reverse_references("not_a_real_table", 1)


@pytest.mark.parametrize(
    "where_sql",
    [
        "1=1; DROP TABLE images",
        "1=1 OR 1=1; DELETE FROM images",
        "id IN (SELECT id FROM images); UPDATE images SET file_path='x'",
        "1=1) ; INSERT INTO images (file_path) VALUES ('x')",
    ],
)
def test_query_table_rejects_mutation_attempts(db, where_sql):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="WHERE clause rejected"):
        repo.query_table("images", where_sql=where_sql)


# ---------------------------------------------------------------------------
# update_cell (DB.9 gated edit mode)
# ---------------------------------------------------------------------------


def test_update_cell_writes_scalar_value(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    image_id = images.add_image(str(p), tags=[])

    repo.update_cell("images", "id", image_id, "filename", "renamed.png")

    _, rows = repo.query_table("images", where_sql=f"id = {image_id}")
    columns, _ = repo.query_table("images")
    filename_idx = columns.index("filename")
    assert rows[0][filename_idx] == "renamed.png"


def test_update_cell_unknown_table_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown table"):
        repo.update_cell("not_a_real_table", "id", 1, "filename", "x")


def test_update_cell_unknown_column_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown column"):
        repo.update_cell("images", "id", 1, "not_a_real_column", "x")


def test_update_cell_unknown_pk_column_raises(db):
    repo = BrowserRepo(db)
    with pytest.raises(ValueError, match="Unknown primary-key column"):
        repo.update_cell("images", "not_a_real_pk", 1, "filename", "x")


def test_update_cell_rejects_primary_key_edit(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    image_id = images.add_image(str(p), tags=[])

    with pytest.raises(ValueError, match="primary-key column"):
        repo.update_cell("images", "id", image_id, "id", 9999)


def test_update_cell_rejects_foreign_key_edit(db, tmp_path):
    images = ImageRepo(db)
    repo = BrowserRepo(db)
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    image_id = images.add_image(str(p), group_name="Trips", tags=[])

    with pytest.raises(ValueError, match="foreign-key column"):
        repo.update_cell("images", "id", image_id, "group_id", 9999)
