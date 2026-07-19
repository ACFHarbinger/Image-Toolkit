"""Tests for the unified DAL (backend/src/database/unified/) — DB.3.

Engine-level tests over a tmp SQLCipher database; no GUI, no JVM.
"""

from pathlib import Path

import pytest

base = pytest.importorskip("base")

from backend.src.database.unified import session  # noqa: E402
from backend.src.database.unified.entity_repo import EntityRepo  # noqa: E402
from backend.src.database.unified.image_repo import ImageRepo  # noqa: E402
from backend.src.database.unified.maintenance import Maintenance  # noqa: E402
from backend.src.database.unified.media_repo import MediaRepo  # noqa: E402
from backend.src.database.unified.search_repo import SearchRepo  # noqa: E402
from backend.src.database.unified.tag_repo import TagRepo  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    handle = base.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    session.ensure_schema(handle)
    yield handle
    handle.close()


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------


def test_session_lifecycle(tmp_path):
    session.close_session()  # ensure clean slate
    db = session.open_session("pw", "salt", db_path=str(tmp_path / "s.db"))
    assert session.is_open()
    assert session.get_session() is db
    # Idempotent for the same path
    assert session.open_session("pw", "salt", db_path=str(tmp_path / "s.db")) is db
    # Different path refused while open
    with pytest.raises(RuntimeError, match="already open"):
        session.open_session("pw", "salt", db_path=str(tmp_path / "other.db"))
    assert db.schema_version() == session.SCHEMA_VERSION
    session.close_session()
    assert not session.is_open()
    with pytest.raises(RuntimeError, match="not open"):
        session.get_session()


def test_ensure_schema_idempotent(db):
    session.ensure_schema(db)  # second application must not raise
    assert db.schema_version() == session.SCHEMA_VERSION
    assert session.fts_enabled(db) == db.has_fts5()


# ---------------------------------------------------------------------------
# media / entity round trips
# ---------------------------------------------------------------------------

LEGACY_ENTRY = {
    "id": "m-1",
    "title": "Cowboy Bebop",
    "type": "Anime",
    "status": "Completed",
    "personal_rating": 9,
    "community_rating": 8.8,
    "year": 1998,
    "episodes": 26,
    "current_episode": 26,
    "genres": "Sci-Fi, Action",
    "tags": "space, bounty hunter",
    "creator": "Sunrise",
    "associated_entities": [],
    "local_file": "/media/bebop/ep01.mkv",
    "web_link": "https://example.org/bebop",
    "review": "classic",
    "image_path": "/imgs/bebop.jpg",
    "episode_list": [
        {"id": "ep-1", "number": 1, "title": "Asteroid Blues",
         "date_watched": "2026-01-01", "rating": 9, "review": "",
         "image_path": "", "local_file": "/media/bebop/ep01.mkv",
         "web_link": ""},
        {"id": "ep-2", "number": 2, "title": "Stray Dog Strut",
         "date_watched": "", "rating": 0, "review": "",
         "image_path": "", "local_file": "", "web_link": ""},
    ],
    "date_added": "2026-07-01",
    "date_watched": "2026-07-02",
    "mal_id": 1,  # legacy ad-hoc key -> must survive via extra
}

LEGACY_ENTITY = {
    "id": "ent-abc12345",
    "name": "Shinichiro Watanabe",
    "first_name": "Shinichiro",
    "last_name": "Watanabe",
    "type": "Person",
    "role": "Director",
    "rating": 10,
    "year": 1965,
    "image_path": "/imgs/watanabe.jpg",
    "notes": "director",
    "credit_list": [
        {"id": "cr-1", "title": "Cowboy Bebop", "role": "Director",
         "year": 1998, "rating": 10, "notes": "", "image_path": ""},
    ],
    "associated_content": [],
    "associated_entities": [],
    "date_added": "2026-07-01",
}


def test_media_round_trip(db):
    repo = MediaRepo(db)
    repo.save_media(LEGACY_ENTRY)
    out = repo.get_media("m-1")

    assert out is not None
    for key in ("title", "type", "status", "year", "creator", "review",
                "web_link", "local_file", "image_path", "date_added",
                "date_watched", "episodes", "current_episode"):
        assert out[key] == LEGACY_ENTRY[key], key
    assert out["mal_id"] == 1                       # extra survived
    assert set(out["genres"].split(", ")) == {"Sci-Fi", "Action"}
    assert set(out["tags"].split(", ")) == {"space", "bounty hunter"}
    eps = out["episode_list"]
    assert [e["id"] for e in eps] == ["ep-1", "ep-2"]
    assert eps[0]["title"] == "Asteroid Blues"

    # Update replaces relations, not duplicates them
    entry2 = dict(LEGACY_ENTRY, genres="Sci-Fi", episode_list=[])
    repo.save_media(entry2)
    out = repo.get_media("m-1")
    assert out["genres"] == "Sci-Fi"
    assert out["episode_list"] == []
    assert repo.count() == 1


def test_integral_ratings_round_trip_as_ints(db):
    """REAL columns must not leak floats back for integral legacy values —
    the card widgets do '"★" * rating' (S210 startup crash regression)."""
    media = MediaRepo(db)
    media.save_media(dict(LEGACY_ENTRY))
    out = media.get_media("m-1")
    assert out["personal_rating"] == 9 and isinstance(out["personal_rating"], int)
    assert isinstance(out["episode_list"][0]["rating"], int)
    # Genuinely fractional values stay floats.
    assert out["community_rating"] == 8.8 and isinstance(out["community_rating"], float)

    entities = EntityRepo(db)
    entities.save_entity(dict(LEGACY_ENTITY))
    ent = entities.get_entity("ent-abc12345")
    assert ent["rating"] == 10 and isinstance(ent["rating"], int)
    assert isinstance(ent["credit_list"][0]["rating"], int)


def test_entity_round_trip_and_associations(db):
    media = MediaRepo(db)
    entities = EntityRepo(db)

    media.save_media(dict(LEGACY_ENTRY))
    ent = dict(LEGACY_ENTITY, associated_content=["m-1"])
    entities.save_entity(ent)

    out = entities.get_entity("ent-abc12345")
    assert out["name"] == "Shinichiro Watanabe"
    assert out["credit_list"][0]["title"] == "Cowboy Bebop"
    assert out["credit_list"][0]["notes"] == ""
    assert out["associated_content"] == ["m-1"]

    # The SAME table serves the media side — no sync loops needed.
    assert media.get_media("m-1")["associated_entities"] == ["ent-abc12345"]

    # Removing the link from the media side is visible from the entity side.
    media.set_entity_links("m-1", [])
    assert entities.get_entity("ent-abc12345")["associated_content"] == []


def test_peer_links_undirected(db):
    entities = EntityRepo(db)
    entities.save_entity({"id": "ent-b", "name": "B"})
    entities.save_entity({"id": "ent-a", "name": "A", "associated_entities": ["ent-b"]})

    # Visible from both sides regardless of insertion direction.
    assert entities.get_entity("ent-a")["associated_entities"] == ["ent-b"]
    assert entities.get_entity("ent-b")["associated_entities"] == ["ent-a"]

    # Self and unknown peers are skipped, not errors.
    entities.set_peer_links("ent-a", ["ent-a", "ent-missing"])
    assert entities.get_entity("ent-a")["associated_entities"] == []


def test_delete_cascades(db):
    media = MediaRepo(db)
    entities = EntityRepo(db)
    media.save_media(dict(LEGACY_ENTRY))
    entities.save_entity(dict(LEGACY_ENTITY, associated_content=["m-1"]))

    assert media.delete_media("m-1")
    assert db.query("SELECT count(*) FROM episodes", ()) == [(0,)]
    assert db.query("SELECT count(*) FROM media_entity", ()) == [(0,)]
    assert db.query("SELECT count(*) FROM media_tags", ()) == [(0,)]
    # Entity untouched
    assert entities.get_entity("ent-abc12345") is not None

    assert entities.delete_entity("ent-abc12345")
    assert db.query("SELECT count(*) FROM credits", ()) == [(0,)]


# ---------------------------------------------------------------------------
# image repo
# ---------------------------------------------------------------------------


def test_image_add_update_and_groups(db, tmp_path):
    repo = ImageRepo(db)
    img = tmp_path / "photo.png"
    img.write_bytes(b"png-bytes")

    image_id = repo.add_image(
        str(img), group_name="Trips", subgroup_name="Beach",
        tags=["sunset", "sea"], width=800, height=600,
    )
    out = repo.get_image_by_path(str(img))
    assert out["id"] == image_id
    assert out["group_name"] == "Trips"
    assert out["subgroup_name"] == "Beach"
    assert out["tags"] == ["sea", "sunset"]
    assert out["file_size"] == len(b"png-bytes")

    # Upsert by path: same id, updated fields
    again = repo.add_image(str(img), tags=["sunset"])
    assert again == image_id
    assert repo.get_image_tags(image_id) == ["sunset"]
    assert repo.count() == 1

    # update_image: None leaves, values replace
    repo.update_image(image_id, subgroup_name="", tags=[])
    out = repo.get_image_by_path(str(img))
    assert out["subgroup_name"] is None
    assert out["group_name"] == "Trips"
    assert out["tags"] == []

    # groups API parity
    assert repo.get_all_groups() == ["Trips"]
    assert repo.get_subgroups_for_group("Trips") == ["Beach"]
    assert repo.get_all_subgroups_detailed() == [("Beach", "Trips")]
    repo.rename_group("Trips", "Voyages")
    assert repo.get_all_groups() == ["Voyages"]
    repo.rename_subgroup("Beach", "Shore", "Voyages")
    assert repo.get_subgroups_for_group("Voyages") == ["Shore"]

    # deleting the group orphans the image (SET NULL), doesn't delete it
    repo.delete_group("Voyages")
    out = repo.get_image_by_path(str(img))
    assert out is not None and out["group_name"] is None
    assert repo.get_all_subgroups() == []  # cascade from group

    repo.update_phash(image_id, -12345)
    assert repo.get_all_phashes() == [(image_id, str(img.absolute()), -12345)]
    assert repo.paths_in_db([str(img), "/nope.png"]) == {str(img.absolute())}

    assert repo.delete_image(image_id)
    assert repo.get_image_by_path(str(img)) is None


# ---------------------------------------------------------------------------
# tag repo
# ---------------------------------------------------------------------------


def test_tag_repo_crud_and_merge(db):
    tags = TagRepo(db)
    tags.add_tag("makoto_shinkai", "Artist")
    tags.add_tag("scenery")
    assert tags.get_all_tags_with_types() == [
        {"name": "makoto_shinkai", "type": "Artist"},
        {"name": "scenery", "type": ""},
    ]
    tags.update_tag_type("scenery", "General")
    tags.rename_tag("scenery", "landscape")
    assert tags.get_all_tags(types=["General"]) == ["landscape"]

    # merge repoints references
    media = MediaRepo(db)
    media.save_media({"id": "m-1", "title": "X", "tags": "landscape"})
    tags.add_tag("Landscape (dup)", "Tag")
    dup_id = tags.get_tag_id("Landscape (dup)")
    db.execute(
        "INSERT INTO media_tags (media_item_id, tag_id) VALUES (?, ?)",
        ("m-1", dup_id),
    )
    tags.merge_tags("Landscape (dup)", "landscape")
    assert "Landscape (dup)" not in tags.get_all_tags()
    rows = db.query(
        "SELECT count(*) FROM media_tags WHERE media_item_id = 'm-1'", ()
    )
    # UNIQUE tag names: the CSV 'landscape' bound to the existing General tag,
    # and the dup's link merged into the same row (INSERT OR IGNORE dedupe).
    assert rows == [(1,)]
    # The listing's tags CSV still reconstructs (non-Genre links).
    assert media.get_media("m-1")["tags"] == "landscape"


# ---------------------------------------------------------------------------
# search repo
# ---------------------------------------------------------------------------


@pytest.fixture()
def populated(db, tmp_path):
    images = ImageRepo(db)
    specs = [
        ("a.png", "Trips", "Beach", ["sunset"]),
        ("b.jpg", "Trips", "City", ["night"]),
        ("c.png", "Art", None, ["sunset", "night"]),
    ]
    for name, group, sub, tag_list in specs:
        p = tmp_path / name
        p.write_bytes(b"x")
        images.add_image(str(p), group_name=group, subgroup_name=sub, tags=tag_list)
    return db


def test_search_images_filters(populated):
    search = SearchRepo(populated)
    assert len(search.search_images()) == 3
    assert {r["filename"] for r in search.search_images(group_name="trips")} == {
        "a.png", "b.jpg"
    }
    assert [r["filename"] for r in search.search_images(subgroup_name="beach")] == ["a.png"]
    assert {r["filename"] for r in search.search_images(tags=["sunset"])} == {
        "a.png", "c.png"
    }
    assert {r["filename"] for r in search.search_images(input_formats=["png"])} == {
        "a.png", "c.png"
    }
    assert [r["filename"] for r in search.search_images(filename_pattern="b")] == ["b.jpg"]
    result = search.search_images(tags=["sunset"], input_formats=["png"], group_name="Art")
    assert [r["filename"] for r in result] == ["c.png"]
    assert result[0]["tags"] == ["night", "sunset"]

    # Test multi-group and multi-subgroup search support
    assert {r["filename"] for r in search.search_images(group_names=["Trips", "Art"])} == {
        "a.png", "b.jpg", "c.png"
    }
    assert {r["filename"] for r in search.search_images(group_names=["Art"])} == {
        "c.png"
    }
    assert {r["filename"] for r in search.search_images(subgroup_names=["Beach", "City"])} == {
        "a.png", "b.jpg"
    }
    assert {r["filename"] for r in search.search_images(group_names=["Trips"], subgroup_names=["Beach"])} == {
        "a.png"
    }



def test_text_search_media_and_entities(db):
    MediaRepo(db).save_media(
        {"id": "m-1", "title": "Cowboy Bebop", "review": "space bounty hunters"}
    )
    EntityRepo(db).save_entity(
        {"id": "e-1", "name": "Yoko Kanno", "notes": "composer"}
    )
    search = SearchRepo(db)
    assert search.search_media_text("bounty") == ["m-1"]
    assert search.search_media_text("cowboy be") == ["m-1"]  # prefix match
    assert search.search_media_text("zelda") == []
    assert search.search_entities_text("kanno") == ["e-1"]
    assert search.search_entities_text('"quoted" AND (junk') == []  # no FTS injection


def test_advanced_media_search(db):
    media = MediaRepo(db)
    entities = EntityRepo(db)
    entities.save_entity({"id": "e-1", "name": "A"})
    media.save_media({"id": "m-1", "title": "One", "genres": "Action, Drama",
                      "tags": "mecha", "associated_entities": ["e-1"]})
    media.save_media({"id": "m-2", "title": "Two", "genres": "Drama", "tags": ""})
    media.save_media({"id": "m-3", "title": "Three", "genres": "Comedy",
                      "tags": "mecha"})
    search = SearchRepo(db)

    # AND: genre Drama AND tag mecha -> only m-1
    assert search.advanced_media_search(
        {"include_genres": ["Drama"], "include_tags": ["mecha"], "match_mode": "AND"}
    ) == ["m-1"]
    # OR: Drama or mecha -> m-1, m-2, m-3
    assert set(search.advanced_media_search(
        {"include_genres": ["Drama"], "include_tags": ["mecha"], "match_mode": "OR"}
    )) == {"m-1", "m-2", "m-3"}
    # Exclusion beats inclusion
    assert search.advanced_media_search(
        {"include_genres": ["Drama"], "exclude_entities": ["e-1"], "match_mode": "AND"}
    ) == ["m-2"]
    # No criteria -> everything
    assert set(search.advanced_media_search({})) == {"m-1", "m-2", "m-3"}


def test_semantic_image_search_with_prefilter(populated):
    np = pytest.importorskip("numpy")
    search = SearchRepo(populated)
    ids = {r["filename"]: r["id"] for r in search.search_images()}
    vecs = {
        "a.png": [1.0, 0.0],
        "b.jpg": [0.9, 0.1],
        "c.png": [0.0, 1.0],
    }
    for name, vec in vecs.items():
        populated.upsert_embedding(
            "image", str(ids[name]), "metaclip", np.array(vec, dtype=np.float32)
        )
    q = np.array([1.0, 0.0], dtype=np.float32)

    hits = search.semantic_image_search(q, top_k=2)
    assert [h[0] for h in hits] == [ids["a.png"], ids["b.jpg"]]
    assert hits[0][2].endswith("a.png")

    # Structured prefilter composes with vector search.
    hits = search.semantic_image_search(q, top_k=5, group_name="Art")
    assert [h[0] for h in hits] == [ids["c.png"]]
    hits = search.semantic_image_search(q, top_k=5, tags=["night"], input_formats=["jpg"])
    assert [h[0] for h in hits] == [ids["b.jpg"]]


# ---------------------------------------------------------------------------
# maintenance
# ---------------------------------------------------------------------------


def test_maintenance_statistics(populated):
    stats = Maintenance(populated).statistics()
    assert stats["total_images"] == 3
    assert stats["total_groups"] == 2
    assert stats["total_subgroups"] == 2
    assert stats["total_tags"] == 2
    assert stats["total_file_size"] == 3
    assert stats["schema_version"] == session.SCHEMA_VERSION


def test_reset_requires_verified_backup(populated, tmp_path, monkeypatch):
    maint = Maintenance(populated)
    from backend.migrations import backup_all

    monkeypatch.setattr(backup_all, "PRE_UNIFIED_DIR", tmp_path / "none")
    with pytest.raises(RuntimeError, match="no backup manifest"):
        maint.reset_database()

    # With a verified backup it wipes rows but keeps schema_meta.
    monkeypatch.setattr(backup_all, "LISTINGS_DB", tmp_path / "l.db")
    (tmp_path / "l.db").write_bytes(b"x")
    monkeypatch.setattr(backup_all, "SECRETS_DIR", tmp_path / "nosecrets")
    monkeypatch.setattr(backup_all, "ENV_FILE", tmp_path / "no.env")
    manifest = backup_all.run_backup(tmp_path / "bk")
    maint.reset_database(
        backup_manifest_path=Path(manifest["backup_dir"]) / "manifest.json"
    )
    assert maint.statistics()["total_images"] == 0
    assert populated.schema_version() == session.SCHEMA_VERSION
