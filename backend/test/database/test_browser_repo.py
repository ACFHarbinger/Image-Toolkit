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
