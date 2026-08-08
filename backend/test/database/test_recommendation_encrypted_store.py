"""Tests for EncryptedSQLiteStore (DB.7 follow-up) -- CRE's
storage layer swapped onto an encrypted base.database.Database handle
instead of a plaintext sqlite3 file, with the retrieval/scoring algorithm
above it left completely untouched.

Mirrors submodules/CRE/tests/test_store.py's coverage of
SQLiteStore, against the same public API.
"""

import sys
from pathlib import Path

import pytest

base = pytest.importorskip("base")

_RE_DIR = Path(__file__).resolve().parents[3] / "submodules" / "CRE"

# backend/test/conftest.py (loaded for every test under backend/test/,
# including this one) already does `import src.constants as udef`, binding
# sys.modules["src"] to Image Toolkit's OWN backend/src -- the exact same
# bare top-level name CRE's package uses for itself. That
# collision doesn't exist at runtime (recommendation_worker.py's
# _ensure_re_on_path() works fine there, since the app never imports this
# conftest.py) -- it's test-collection-only. Temporarily evict the cached
# "src"/"src.*" modules so CRE's own "src" package is
# what actually gets imported here, then restore Image Toolkit's originals
# afterward so no other test in this session is affected.
_saved_src_modules = {
    name: mod for name, mod in sys.modules.items()
    if name == "src" or name.startswith("src.")
}
for name in _saved_src_modules:
    del sys.modules[name]
if str(_RE_DIR) not in sys.path:
    sys.path.insert(0, str(_RE_DIR))

from src.core.schema import EmbeddedItem, MediaItem  # noqa: E402  # pyrefly: ignore [missing-import]
from src.data.store import EncryptedSQLiteStore  # noqa: E402  # pyrefly: ignore [missing-import]

# Evict CRE's "src.*" entries in turn and restore Image
# Toolkit's originals -- everything this test file needs from RE's "src"
# package is already bound to the local names imported above.
for name in list(sys.modules):
    if name == "src" or name.startswith("src."):
        del sys.modules[name]
sys.modules.update(_saved_src_modules)


@pytest.fixture()
def db(tmp_path):
    handle = base.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    yield handle
    handle.close()


def _make_item(item_id: str, title: str) -> EmbeddedItem:
    item = MediaItem.model_validate(
        {
            "id": item_id,
            "title": title,
            "type": "movie",
            "status": "watched",
            "rating": 9.0,
            "year": 1995,
            "episodes": 1,
            "genres": "Sci-Fi, Action",
            "tags": "cyberpunk",
        }
    )
    return EmbeddedItem(
        item=item,
        dense_vector=[0.1, 0.2, 0.3],
        sparse_indices=[1, 2, 3],
        sparse_values=[0.5, 0.3, 0.2],
    )


class TestCreateCollection:
    def test_creates_new_table(self, db):
        store = EncryptedSQLiteStore(db)
        assert store.create_collection() is True

    def test_idempotent_on_existing_table(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        assert store.create_collection() is False

    def test_collection_info_after_creation(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        info = store.collection_info()
        assert info["points_count"] == 0
        assert "encrypted" in info["storage"]

    def test_collection_is_queryable_after_creation(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        assert store.fetch_all() == []

    def test_uses_its_own_table_name_not_the_unified_schema(self, db):
        """Must not collide with the unified schema's own tables."""
        from backend.src.database.unified import session

        session.ensure_schema(db)
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        # both the unified schema's tables and rec_engine_items coexist
        tables = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'", ())}
        assert "images" in tables  # unified schema
        assert "rec_engine_items" in tables  # this store


class TestUpsert:
    def test_upsert_stores_items(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        items = [_make_item(f"id-{i}", f"Title {i}") for i in range(3)]
        assert store.upsert(items) == 3

    def test_upsert_reflected_in_count(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.upsert([_make_item("id-1", "Title 1")])
        assert store.collection_info()["points_count"] == 1

    def test_upsert_payload_contains_required_fields(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.upsert([_make_item("id-1", "Title 1")])
        rows = store.fetch_all()
        assert len(rows) == 1
        row = rows[0]
        for key in ("id", "title", "type", "watch_status", "rating", "year_released", "genres", "tags"):
            assert key in row
        assert row["genres"] == ["Sci-Fi", "Action"]

    def test_upsert_empty_list_returns_zero(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        assert store.upsert([]) == 0

    def test_upsert_respects_batch_size(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        items = [_make_item(f"id-{i}", f"Title {i}") for i in range(3)]
        assert store.upsert(items, batch_size=2) == 3
        assert store.collection_info()["points_count"] == 3

    def test_upsert_is_idempotent(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        item = [_make_item("id-1", "Title 1")]
        store.upsert(item)
        store.upsert(item)
        assert store.collection_info()["points_count"] == 1


class TestDelete:
    def test_delete_removes_item(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.upsert([_make_item("id-1", "Title 1")])
        store.delete("id-1")
        assert store.collection_info()["points_count"] == 0

    def test_delete_nonexistent_is_silent(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.delete("nonexistent-id")


class TestFetchFiltered:
    def test_excludes_vector_columns(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.upsert([_make_item("id-1", "Title 1")])
        rows = store.fetch_filtered()
        assert len(rows) == 1
        assert "dense_vector" not in rows[0]
        assert rows[0]["title"] == "Title 1"

    def test_respects_limit(self, db):
        store = EncryptedSQLiteStore(db)
        store.create_collection()
        store.upsert([_make_item(f"id-{i}", f"Title {i}") for i in range(5)])
        rows = store.fetch_filtered(limit=2)
        assert len(rows) == 2
