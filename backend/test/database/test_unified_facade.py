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
    assert db.get_all_tags_with_types() == [{"name": "t1", "type": "Artist"}]

    db.rename_group("G", "G2")
    db.rename_subgroup("S", "S2", "G2")
    db.rename_tag("t1", "t2")
    db.update_tag_type("t2", "Meta")
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


def test_maintenance_and_gated_reset(populated, tmp_path, monkeypatch):
    db, _ = populated
    db.maintenance_vacuum(full=False)
    db.maintenance_reindex()
    db.close()  # no-op — session stays usable
    assert db.get_statistics()["total_images"] == 2

    from backend.migrations import backup_all
    monkeypatch.setattr(backup_all, "PRE_UNIFIED_DIR", tmp_path / "none")
    with pytest.raises(RuntimeError, match="no backup manifest"):
        db.reset_database()
