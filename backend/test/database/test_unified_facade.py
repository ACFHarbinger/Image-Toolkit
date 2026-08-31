"""Tests for UnifiedImageDatabase — the PgvectorImageDatabase-compatible
facade the image tabs consume via db_tab_ref.db (DB.6)."""

import pytest

base = pytest.importorskip("base")

from backend.src.database.unified import session  # noqa: E402
from backend.src.database.unified.facade import UnifiedImageDatabase  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    handle = base.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    session.ensure_schema(handle)
    yield UnifiedImageDatabase(handle)
    handle.close()


@pytest.fixture()
def populated(db, tmp_path):
    for name, group, sub, tags in (
        ("a.png", "Trips", "Beach", ["sunset"]),
        ("b.jpg", "Trips", None, ["night"]),
    ):
        p = tmp_path / name
        p.write_bytes(b"x")
        # exact legacy call shape used by ScanMetadataTab.perform_upsert_operation
        db.add_image(str(p), embedding=None, group_name=group,
                     subgroup_name=sub, tags=tags, width=10, height=10)
    return db, tmp_path


def test_search_images_legacy_call_shape(populated):
    db, tmp_path = populated
    # exact query_params dict built by SearchTab.perform_search
    results = db.search_images(
        group_name="Trips",
        subgroup_name=None,
        filename_pattern=None,
        tags=[],
        input_formats=None,
        limit=10000,
    )
    assert len(results) == 2
    assert {"file_path", "filename", "tags", "group_name"} <= set(results[0])

    # legacy signature also carried query_vector — must be tolerated
    results = db.search_images(query_vector=None, tags=["sunset"], limit=10)
    assert [r["filename"] for r in results] == ["a.png"]


def test_image_lifecycle_via_facade(populated):
    db, tmp_path = populated
    img = db.get_image_by_path(str(tmp_path / "a.png"))
    assert img and img["group_name"] == "Trips"
    assert db.get_image_tags(img["id"]) == ["sunset"]

    db.update_image(img["id"], group_name="Art", tags=["repainted"])
    assert db.get_image_by_path(str(tmp_path / "a.png"))["group_name"] == "Art"

    db.update_phash(img["id"], 99)
    db.delete_image(img["id"])
    assert db.get_image_by_path(str(tmp_path / "a.png")) is None


def test_vocabulary_management_parity(db):
    db.add_group("G")
    db.add_subgroup("S", "G")
    db.add_tag("t1", "Artist")
    assert db.get_all_groups() == ["G"]
    assert db.get_all_subgroups_detailed() == [("S", "G")]
    assert db.get_subgroups_for_group("G") == ["S"]
    assert db.get_all_tags_with_categories() == [
        {"name": "t1", "category": "Artist", "color": "#5865f2"}
    ]

    db.rename_group("G", "G2")
    db.rename_subgroup("S", "S2", "G2")
    db.rename_tag("t1", "t2")
    db.update_tag_category("t2", "Meta")
    assert db.get_all_tags() == ["t2"]

    # duplicate rename surfaces as an error containing UNIQUE (DatabaseTab
    # matches on that string now that psycopg2.UniqueViolation is gone)
    db.add_group("other")
    with pytest.raises(Exception, match="UNIQUE"):
        db.rename_group("other", "G2")

    db.delete_tag("t2")
    db.delete_subgroup("S2", "G2")
    db.delete_group("G2")
    assert db.get_all_groups() == ["other"]


def test_merge_tags_facade(populated):
    """DB.8c: Management's tag-merge tool, exercised through the facade
    (TagRepo.merge_tags already existed and was tested at the repo level;
    this checks it's actually reachable from db.merge_tags(), the way the
    GUI calls it)."""
    db, tmp_path = populated
    p = tmp_path / "dup.png"
    p.write_bytes(b"x")
    db.add_image(str(p), embedding=None, tags=["sunset (dup)"])
    db.add_tag("sunset")

    db.merge_tags("sunset (dup)", "sunset")

    assert "sunset (dup)" not in db.get_all_tags()
    img = db.get_image_by_path(str(p))
    assert img["tags"] == ["sunset"]


def test_statistics_banner_keys(populated):
    db, _ = populated
    stats = db.get_statistics()
    # keys read by DatabaseTab.update_statistics
    for key in ("total_images", "total_tags", "total_groups",
                "total_subgroups", "total_file_size", "last_sync_date"):
        assert key in stats
    assert stats["total_images"] == 2
    # unified store returns ISO text (or None) — never a datetime
    assert stats["last_sync_date"] is None or isinstance(stats["last_sync_date"], str)


def test_transaction_batches_writes(db, tmp_path):
    """DB.6 P3b: UnifiedImageDatabase.transaction() lets Scan & Tag's
    upsert batch every write into one commit instead of one per image."""
    paths = []
    for name in ("t1.png", "t2.png", "t3.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        paths.append(str(p))

    with db.transaction():
        for p in paths:
            db.add_image(p, embedding=None, group_name="G", subgroup_name=None,
                         tags=["x"], width=1, height=1)

    assert db.get_statistics()["total_images"] == 3
    for p in paths:
        assert db.get_image_by_path(p) is not None

    # a failure mid-transaction must roll back every write in the block
    with pytest.raises(ValueError), db.transaction():
        db.add_image(str(tmp_path / "t4.png"), embedding=None,
                     group_name="G", subgroup_name=None, tags=[],
                     width=1, height=1)
        raise ValueError("boom")
    assert db.get_image_by_path(str(tmp_path / "t4.png")) is None
    assert db.get_statistics()["total_images"] == 3


def test_maintenance_and_gated_reset(populated, tmp_path, monkeypatch):
    db, _ = populated
    db.maintenance_vacuum(full=False)
    db.maintenance_reindex()
    db.close()  # no-op — session stays usable
    assert db.get_statistics()["total_images"] == 2

    from backend.backups import backup_all
    monkeypatch.setattr(backup_all, "PRE_UNIFIED_DIR", tmp_path / "none")
    with pytest.raises(RuntimeError, match="no backup manifest"):
        db.reset_database()


def test_semantic_search_facade_surface(populated):
    """DB.7: the facade methods ImageEmbeddingWorker/the Management panel
    button/Search tab consume, exercised through the exact same call
    shapes those callers use."""
    np = pytest.importorskip("numpy")
    db, tmp_path = populated
    ids = {r["file_path"]: r["id"] for r in db.search_images(limit=10000)}

    assert db.count_unembedded_images("openclip") == 2
    pending = db.list_unembedded_images("openclip")
    assert {p for _, p in pending} == set(ids)

    a_path = str((tmp_path / "a.png").absolute())
    b_path = str((tmp_path / "b.jpg").absolute())
    db.upsert_image_embedding(ids[a_path], "openclip", np.array([1.0, 0.0], dtype=np.float32))
    db.upsert_image_embedding(ids[b_path], "openclip", np.array([0.9, 0.1], dtype=np.float32))
    assert db.count_unembedded_images("openclip") == 0

    hits = db.semantic_image_search(
        np.array([1.0, 0.0], dtype=np.float32), top_k=2, model="openclip"
    )
    assert [h[0] for h in hits] == [ids[a_path], ids[b_path]]
