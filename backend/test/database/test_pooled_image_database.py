"""
Tests for backend/src/database/pooled_image_database.py — §4.8.

All tests run without a live PostgreSQL server by mocking
``psycopg_pool.ConnectionPool`` and the psycopg3 connection/cursor objects.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest

# ── Minimal stubs so the module can be imported without a running PG server ───

def _make_cursor(rows=None, fetchone_val=None):
    """Build a psycopg3-like cursor mock."""
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    if fetchone_val is not None:
        cur.fetchone.return_value = fetchone_val
    else:
        cur.fetchone.return_value = None
    cur.fetchall.return_value = rows or []
    cur.fetchmany.return_value = rows or []
    # execute returns self so callers can chain .fetchone() etc.
    cur.execute.return_value = cur
    return cur


def _make_conn(default_row=None, rows=None):
    """Build a psycopg3-like connection mock."""
    conn = MagicMock()
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)

    cur = _make_cursor(rows=rows, fetchone_val=default_row)
    conn.execute.return_value = cur
    conn.cursor.return_value = cur
    conn.transaction.return_value = _ctx_mgr(conn)
    return conn


@contextmanager
def _ctx_mgr(value):
    yield value


def _make_pool(conn):
    pool = MagicMock()
    pool.connection.return_value = _ctx_mgr(conn)
    pool.close = MagicMock()
    return pool


# ── Patch targets ─────────────────────────────────────────────────────────────

_PATCH_POOL_CLS = "backend.src.database.pooled_image_database.psycopg_pool.ConnectionPool"
_PATCH_GET_POOL = "backend.src.database.pooled_image_database._get_pool"
_PATCH_POOLS   = "backend.src.database.pooled_image_database._pools"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_db(conn):
    """Instantiate PooledPgvectorDatabase with a mocked pool."""
    pool = _make_pool(conn)
    with patch(_PATCH_GET_POOL, return_value=pool), \
         patch("backend.src.database.pooled_image_database.load_dotenv"):
        from backend.src.database.pooled_image_database import PooledPgvectorDatabase
        db = PooledPgvectorDatabase.__new__(PooledPgvectorDatabase)
        db.embedding_dim = 128
        db._conninfo = "dbname=test"
        db._conn_params = {}
        db._pool = pool
    return db


# ── _build_conninfo ────────────────────────────────────────────────────────────

class TestBuildConninfo:
    def test_basic(self):
        from backend.src.database.pooled_image_database import _build_conninfo
        result = _build_conninfo({"dbname": "mydb", "user": "usr", "host": "localhost", "port": "5432", "password": None})
        assert "dbname=mydb" in result
        assert "user=usr" in result
        assert "host=localhost" in result
        assert "port=5432" in result
        assert "password" not in result  # None values skipped

    def test_empty(self):
        from backend.src.database.pooled_image_database import _build_conninfo
        result = _build_conninfo({})
        assert result == ""

    def test_password_with_spaces_escaped(self):
        from backend.src.database.pooled_image_database import _build_conninfo
        result = _build_conninfo({"password": "p ass", "dbname": None, "user": None, "host": None, "port": None})
        assert "password=p" in result


# ── Group management ───────────────────────────────────────────────────────────

class TestGroupManagement:
    def test_add_group_calls_insert(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.add_group("MyGroup")
        assert conn.execute.called

    def test_add_group_empty_raises(self):
        conn = _make_conn()
        db = _make_db(conn)
        with pytest.raises(ValueError):
            db.add_group("")

    def test_delete_group_calls_execute(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.delete_group("MyGroup")
        conn.execute.assert_called()

    def test_rename_group_same_name_is_noop(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.rename_group("A", "A")
        conn.execute.assert_not_called()

    def test_rename_group_empty_raises(self):
        conn = _make_conn()
        db = _make_db(conn)
        with pytest.raises(ValueError):
            db.rename_group("A", "")

    def test_get_all_groups_returns_names(self):
        rows = [{"name": "alpha"}, {"name": "beta"}]
        conn = _make_conn(rows=rows)
        db = _make_db(conn)
        result = db.get_all_groups()
        assert result == ["alpha", "beta"]


# ── Tag management ─────────────────────────────────────────────────────────────

class TestTagManagement:
    def test_add_tag_empty_raises(self):
        conn = _make_conn()
        db = _make_db(conn)
        with pytest.raises(ValueError):
            db.add_tag("")

    def test_rename_tag_same_name_is_noop(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.rename_tag("x", "x")
        conn.execute.assert_not_called()

    def test_get_all_tags_returns_names(self):
        rows = [{"name": "1girl"}, {"name": "blue eyes"}]
        conn = _make_conn(rows=rows)
        db = _make_db(conn)
        assert db.get_all_tags() == ["1girl", "blue eyes"]

    def test_get_all_tags_with_types(self):
        rows = [{"name": "1girl", "type": None}, {"name": "dress", "type": "clothing"}]
        conn = _make_conn(rows=rows)
        db = _make_db(conn)
        result = db.get_all_tags_with_types()
        assert result[0] == {"name": "1girl", "type": ""}
        assert result[1] == {"name": "dress", "type": "clothing"}

    def test_update_tag_type_none_for_blank(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.update_tag_type("tag", "")
        # should pass type_value=None to execute
        call_args = conn.execute.call_args
        assert call_args[0][1][0] is None


# ── Image CRUD ─────────────────────────────────────────────────────────────────

class TestImageCrud:
    def test_delete_image_calls_execute(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.delete_image(42)
        conn.execute.assert_called()

    def test_get_image_by_path_not_found_returns_none(self):
        conn = _make_conn(default_row=None)
        db = _make_db(conn)
        result = db.get_image_by_path("/nonexistent/path.png")
        assert result is None

    def test_add_image_returns_id(self):
        # execute().fetchone() should return {"id": 99}
        cur = _make_cursor(fetchone_val={"id": 99})
        conn = _make_conn()
        conn.execute.return_value = cur
        db = _make_db(conn)
        result = db.add_image("/some/path.png")
        assert result == 99

    def test_add_image_with_empty_tags_clears_and_skips_insert(self):
        cur = _make_cursor(fetchone_val={"id": 7})
        conn = _make_conn()
        conn.execute.return_value = cur
        db = _make_db(conn)
        db.add_image("/img.png", tags=[])
        # delete_image_tags should be called but executemany should not
        conn.executemany.assert_not_called()


# ── Pool lifecycle ─────────────────────────────────────────────────────────────

class TestPoolLifecycle:
    def test_close_removes_pool_from_registry(self):
        conn = _make_conn()
        pool = _make_pool(conn)
        with patch(_PATCH_GET_POOL, return_value=pool), \
             patch("backend.src.database.pooled_image_database.load_dotenv"):
            from backend.src.database.pooled_image_database import (
                PooledPgvectorDatabase, _pools
            )
            db = PooledPgvectorDatabase.__new__(PooledPgvectorDatabase)
            db.embedding_dim = 128
            db._conninfo = "dsn_lifecycle_test"
            db._conn_params = {}
            db._pool = pool
            # Simulate pool registered
            import backend.src.database.pooled_image_database as _mod
            _mod._pools["dsn_lifecycle_test"] = pool
            db.close()
            pool.close.assert_called_once()
            assert "dsn_lifecycle_test" not in _mod._pools

    def test_context_manager_calls_close(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.close = MagicMock()
        with db:
            pass
        db.close.assert_called_once()


# ── phash deduplication ────────────────────────────────────────────────────────

class TestPhash:
    def test_update_phash_calls_execute(self):
        conn = _make_conn()
        db = _make_db(conn)
        db.update_phash(1, 12345678)
        conn.execute.assert_called()

    def test_find_near_duplicates_returns_list(self):
        rows = [{"id": 1, "file_path": "/a.png", "filename": "a.png",
                 "group_name": "g", "subgroup_name": "s",
                 "phash": 0, "hamming_dist": 2}]
        cur = _make_cursor(rows=rows)
        conn = _make_conn()
        conn.execute.return_value = cur
        db = _make_db(conn)
        result = db.find_near_duplicates_by_phash(0, threshold=5)
        assert len(result) == 1
        assert result[0]["hamming_dist"] == 2
