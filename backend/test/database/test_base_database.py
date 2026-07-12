"""Tests for the base.database session-keyed SQLCipher engine (DB.2).

Pure engine tests — no GUI, no JVM. Uses tmp_path databases throughout.
"""

import threading
import time
from pathlib import Path

import numpy as np
import pytest

base = pytest.importorskip("base")

SCHEMA_SQL = (
    Path(__file__).resolve().parents[2]
    / "src" / "database" / "unified" / "schema.sql"
).read_text()

PASSWORD = "test-password"
SALT = "test-account"


@pytest.fixture()
def db(tmp_path):
    handle = base.database.Database(str(tmp_path / "lib.db"), PASSWORD, SALT)
    yield handle
    handle.close()


def test_open_creates_file_and_is_encrypted(tmp_path):
    path = tmp_path / "lib.db"
    db = base.database.Database(str(path), PASSWORD, SALT)
    db.apply_ddl("CREATE TABLE t (x TEXT);")
    db.execute("INSERT INTO t VALUES (?)", ("needle-plaintext",))
    db.close()
    raw = path.read_bytes()
    assert b"needle-plaintext" not in raw          # encrypted at rest
    assert not raw.startswith(b"SQLite format 3")  # no plaintext header


def test_wrong_password_rejected(tmp_path):
    path = str(tmp_path / "lib.db")
    db = base.database.Database(path, PASSWORD, SALT)
    db.apply_ddl("CREATE TABLE t (x TEXT);")
    db.close()
    with pytest.raises(RuntimeError, match="wrong password"):
        base.database.Database(path, "not-the-password", SALT)
    with pytest.raises(RuntimeError, match="wrong password"):
        base.database.Database(path, PASSWORD, "not-the-salt")


def test_query_roundtrips_all_types(db):
    db.apply_ddl("CREATE TABLE t (i INTEGER, f REAL, s TEXT, b BLOB, n TEXT);")
    db.execute(
        "INSERT INTO t VALUES (?, ?, ?, ?, ?)",
        (42, 2.5, "héllo", b"\x00\xff", None),
    )
    rows = db.query("SELECT i, f, s, b, n FROM t", ())
    assert rows == [(42, 2.5, "héllo", b"\x00\xff", None)]


def test_param_count_mismatch_raises(db):
    db.apply_ddl("CREATE TABLE t (x TEXT);")
    with pytest.raises(ValueError, match="expects 1 parameters, got 2"):
        db.execute("INSERT INTO t VALUES (?)", ("a", "b"))


def test_executemany_is_atomic(db):
    db.apply_ddl("CREATE TABLE t (x INTEGER NOT NULL);")
    with pytest.raises(RuntimeError):
        # Third row violates NOT NULL — the first two must roll back too.
        db.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (None,)])
    assert db.query("SELECT count(*) FROM t", ()) == [(0,)]

    db.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    assert db.query("SELECT count(*) FROM t", ()) == [(3,)]


def test_explicit_transactions(db):
    db.apply_ddl("CREATE TABLE t (x TEXT);")
    db.begin()
    assert db.in_transaction
    db.execute("INSERT INTO t VALUES (?)", ("a",))
    db.rollback()
    assert not db.in_transaction
    assert db.query("SELECT count(*) FROM t", ()) == [(0,)]

    db.begin()
    db.execute("INSERT INTO t VALUES (?)", ("b",))
    db.commit()
    assert db.query("SELECT * FROM t", ()) == [("b",)]


def test_schema_ddl_applies_and_stamps_version(db):
    assert db.schema_version() == 0
    db.apply_ddl(SCHEMA_SQL)
    db.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1')",
        (),
    )
    assert db.schema_version() == 1
    stats = db.statistics()
    assert stats["schema_version"] == 1
    assert "media_items" in stats["tables"]
    assert "images" in stats["tables"]
    assert db.integrity_check()


def test_foreign_keys_enforced(db):
    db.apply_ddl(SCHEMA_SQL)
    with pytest.raises(RuntimeError, match="FOREIGN KEY"):
        db.execute(
            "INSERT INTO episodes (id, media_item_id) VALUES (?, ?)",
            ("ep1", "no-such-media"),
        )
    # Cascade: deleting the parent removes children.
    db.execute(
        "INSERT INTO media_items (id, title) VALUES (?, ?)", ("m1", "Show")
    )
    db.execute(
        "INSERT INTO episodes (id, media_item_id) VALUES (?, ?)", ("ep1", "m1")
    )
    db.execute("DELETE FROM media_items WHERE id = ?", ("m1",))
    assert db.query("SELECT count(*) FROM episodes", ()) == [(0,)]


def test_embeddings_knn(db):
    db.apply_ddl(SCHEMA_SQL)
    vecs = {
        "1": [1.0, 0.0, 0.0],
        "2": [0.9, 0.1, 0.0],
        "3": [0.0, 1.0, 0.0],
    }
    for oid, v in vecs.items():
        db.upsert_embedding("image", oid, "m", np.array(v, dtype=np.float32))

    q = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    hits = db.knn("image", "m", q, top_k=2)
    assert [h[0] for h in hits] == ["1", "2"]
    assert hits[0][1] == pytest.approx(1.0)

    # Prefilter restricts candidates before scoring.
    hits = db.knn("image", "m", q, top_k=5, prefilter_sql="SELECT '3'")
    assert [h[0] for h in hits] == ["3"]

    # Upsert replaces in place.
    db.upsert_embedding("image", "3", "m", np.array([1.0, 0, 0], dtype=np.float32))
    hits = db.knn("image", "m", q, top_k=1, prefilter_sql="SELECT '3'")
    assert hits[0][1] == pytest.approx(1.0)

    # Dimension mismatches are skipped, other owner types invisible.
    db.upsert_embedding("image", "4", "m", np.array([1.0, 0], dtype=np.float32))
    db.upsert_embedding("entity", "e1", "m", np.array([1.0, 0, 0], dtype=np.float32))
    ids = {h[0] for h in db.knn("image", "m", q, top_k=10)}
    assert ids == {"1", "2", "3"}


def test_kdf_once_per_session(tmp_path):
    """The KDF cost is paid in the constructor, not per call."""
    path = str(tmp_path / "lib.db")
    t0 = time.perf_counter()
    db = base.database.Database(path, PASSWORD, SALT)
    ctor_time = time.perf_counter() - t0

    db.apply_ddl("CREATE TABLE t (x INTEGER);")
    db.execute("INSERT INTO t VALUES (1)", ())
    t0 = time.perf_counter()
    for _ in range(50):
        db.query("SELECT x FROM t", ())
    fifty_queries = time.perf_counter() - t0
    db.close()

    # 50 keyed queries must be far cheaper than one Argon2id derivation.
    assert fifty_queries < ctor_time


def test_concurrent_workers_smoke(db):
    """Qt-worker-style concurrent access must not corrupt or crash."""
    db.apply_ddl("CREATE TABLE t (thread INTEGER, n INTEGER);")
    errors = []

    def work(tid):
        try:
            for n in range(50):
                db.execute("INSERT INTO t VALUES (?, ?)", (tid, n))
                db.query("SELECT count(*) FROM t", ())
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert db.query("SELECT count(*) FROM t", ()) == [(200,)]
    assert db.integrity_check()


def test_closed_db_raises(tmp_path):
    db = base.database.Database(str(tmp_path / "lib.db"), PASSWORD, SALT)
    db.close()
    assert not db.is_open
    with pytest.raises(RuntimeError, match="closed"):
        db.query("SELECT 1", ())


def test_context_manager(tmp_path):
    with base.database.Database(str(tmp_path / "lib.db"), PASSWORD, SALT) as db:
        assert db.is_open
    assert not db.is_open


def test_fts5_available_and_functional(db):
    """The build must ship FTS5 — search_repo depends on it (DB.1 note 8)."""
    assert db.has_fts5()
    db.apply_ddl(SCHEMA_SQL)
    fts_sql = (
        Path(__file__).resolve().parents[2]
        / "src" / "database" / "unified" / "schema_fts.sql"
    ).read_text()
    db.apply_ddl(fts_sql)
    db.execute(
        "INSERT INTO media_items (id, title, review) VALUES (?, ?, ?)",
        ("m1", "Cowboy Bebop", "space bounty hunters"),
    )
    rows = db.query(
        "SELECT m.id FROM media_fts f JOIN media_items m ON m.rowid = f.rowid "
        "WHERE media_fts MATCH ?",
        ("bounty",),
    )
    assert rows == [("m1",)]
