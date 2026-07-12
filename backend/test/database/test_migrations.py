"""Tests for migrations 001–004 + runner (Phase DB, DB.4).

Builds a real legacy listings_secure.db fixture through base.secret (the
same API the app used to write it) and migrates it into a tmp library.db.
The pgvector step is exercised through an injected data provider — no
PostgreSQL server involved.
"""

import json
from pathlib import Path

import pytest

base = pytest.importorskip("base")

from backend.migrations import backup_all, runner  # noqa: E402
from backend.migrations import create_library_db, migrate_listings  # noqa: E402
from backend.migrations import migrate_pgvector, verify_migration  # noqa: E402
from backend.src.database.unified.entity_repo import EntityRepo  # noqa: E402
from backend.src.database.unified.media_repo import MediaRepo  # noqa: E402

PASSWORD = "pw"
SALT = "salt"


# ---------------------------------------------------------------------------
# Legacy fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def legacy_db(tmp_path):
    """A listings_secure.db written exactly the way the app wrote it."""
    path = str(tmp_path / "listings_secure.db")

    def put(listing_id, category, title, meta, date_added="2026-07-01"):
        base.secret.insert_listing_secure(
            path, PASSWORD, SALT, listing_id, category, title,
            json.dumps(meta, ensure_ascii=False), date_added, [],
        )

    put("m-1", "Anime", "Cowboy Bebop", {
        "id": "m-1", "title": "Cowboy Bebop", "type": "Anime",
        "status": "Completed", "personal_rating": 9, "year": 1998,
        "episodes": 26, "current_episode": 26,
        "genres": "Sci-Fi, Action", "tags": "space",
        "creator": "Sunrise", "associated_entities": ["ent-1", "ent-GONE"],
        "local_file": "/m/bebop.mkv", "web_link": "", "review": "",
        "image_path": "",
        "episode_list": [
            {"id": "ep-1", "number": 1, "title": "Asteroid Blues",
             "date_watched": "2026-01-01", "rating": 9, "review": "",
             "image_path": "", "local_file": "", "web_link": ""},
        ],
        "date_added": "2026-07-01", "mal_id": 1,
    })
    put("m-2", "Movie", "Your Name", {
        "id": "m-2", "title": "Your Name", "type": "Movie",
        "genres": "Romance", "tags": "", "associated_entities": [],
        "date_added": "2026-07-02",
    })
    put("ent-1", "Entity", "Shinichiro Watanabe", {
        "id": "ent-1", "name": "Shinichiro Watanabe", "type": "Person",
        "role": "Director", "rating": 10,
        "credit_list": [{"id": "cr-1", "title": "Cowboy Bebop",
                         "role": "Director", "year": 1998, "rating": 10,
                         "notes": "", "image_path": ""}],
        "associated_content": ["m-1"], "associated_entities": ["ent-2"],
        "date_added": "2026-07-01",
    })
    put("ent-2", "Entity", "Yoko Kanno", {
        "id": "ent-2", "name": "Yoko Kanno", "type": "Person",
        "role": "Other", "associated_content": ["m-1", "m-MISSING"],
        "associated_entities": ["ent-1"], "date_added": "2026-07-01",
    })
    return path


FAKE_PG = {
    "groups": [("Trips",), ("Art",)],
    "subgroups": [("Beach", "Trips")],
    "tags": [("sunset", "General"), ("makoto_shinkai", "Artist")],
    "images": [
        ("/pics/a.png", "a.png", 100, 800, 600, "Trips", "Beach",
         "2025-01-01 10:00:00", "2025-06-01 10:00:00", -42),
        ("/pics/b.jpg", "b.jpg", 200, None, None, "Art", None,
         "2025-02-01 10:00:00", None, None),
        ("/pics/c.png", "c.png", 300, 10, 10, None, None,
         "2025-03-01 10:00:00", None, 7),
    ],
    "image_tags": [("/pics/a.png", "sunset"), ("/pics/b.jpg", "makoto_shinkai")],
}


def fake_pg_provider():
    return {k: list(v) for k, v in FAKE_PG.items()}


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------


def test_001_create_library_db(tmp_path):
    lib = str(tmp_path / "library.db")
    report = create_library_db.run(PASSWORD, SALT, db_path=lib)
    assert report["schema_version"] == 1
    assert report["integrity_ok"]
    # Idempotent
    assert create_library_db.run(PASSWORD, SALT, db_path=lib)["integrity_ok"]


def test_002_migrate_listings_round_trip(tmp_path, legacy_db):
    lib = str(tmp_path / "library.db")
    report = migrate_listings.run(
        PASSWORD, SALT, db_path=lib, legacy_db_path=legacy_db
    )
    assert not report["skipped"]
    assert report["media_migrated"] == 2
    assert report["entities_migrated"] == 2

    db = base.database.Database(lib, PASSWORD, SALT)
    try:
        media = MediaRepo(db)
        entities = EntityRepo(db)

        bebop = media.get_media("m-1")
        assert bebop["title"] == "Cowboy Bebop"
        assert bebop["status"] == "Completed"
        assert set(bebop["genres"].split(", ")) == {"Sci-Fi", "Action"}
        assert bebop["episode_list"][0]["title"] == "Asteroid Blues"
        assert bebop["mal_id"] == 1                      # extra survived
        # ent-1 from m-1's own list; ent-2 healed from ent-2's
        # associated_content (legacy sides could disagree — the single M2M
        # table unions them). ent-GONE is dangling: dropped but parked.
        assert bebop["associated_entities"] == ["ent-1", "ent-2"]
        assert bebop["_dangling_associated_entities"] == ["ent-GONE"]

        watanabe = entities.get_entity("ent-1")
        assert watanabe["credit_list"][0]["title"] == "Cowboy Bebop"
        assert watanabe["associated_content"] == ["m-1"]
        assert watanabe["associated_entities"] == ["ent-2"]

        kanno = entities.get_entity("ent-2")
        assert kanno["associated_content"] == ["m-1"]
        assert kanno["_dangling_associated_content"] == ["m-MISSING"]

        # Dangling report matches
        assert report["dangling_references"] == {
            "media:m-1": ["ent-GONE"],
            "entity:ent-2": ["m-MISSING"],
        }
    finally:
        db.close()

    # Idempotent: re-running changes nothing.
    report2 = migrate_listings.run(
        PASSWORD, SALT, db_path=lib, legacy_db_path=legacy_db
    )
    assert report2["media_in_target"] == 2
    assert report2["entities_in_target"] == 2


def test_002_skips_when_legacy_missing(tmp_path):
    report = migrate_listings.run(
        PASSWORD, SALT,
        db_path=str(tmp_path / "library.db"),
        legacy_db_path=str(tmp_path / "nope.db"),
    )
    assert report["skipped"]


def test_003_migrate_pgvector_with_provider(tmp_path):
    lib = str(tmp_path / "library.db")
    report = migrate_pgvector.run(
        PASSWORD, SALT, db_path=lib, provider=fake_pg_provider
    )
    assert not report["skipped"]
    assert report["migrated"]["images"] == 3
    assert report["migrated"]["image_tags"] == 2

    db = base.database.Database(lib, PASSWORD, SALT)
    try:
        rows = db.query(
            "SELECT i.file_path, i.file_size, i.phash, g.name, s.name, "
            "i.date_added FROM images i "
            "LEFT JOIN groups g ON g.id = i.group_id "
            "LEFT JOIN subgroups s ON s.id = i.subgroup_id "
            "ORDER BY i.file_path", (),
        )
        assert rows[0] == ("/pics/a.png", 100, -42, "Trips", "Beach",
                           "2025-01-01 10:00:00")   # dates preserved
        assert rows[1][3] == "Art" and rows[1][4] is None
        assert rows[2][3] is None
        tag_rows = db.query(
            "SELECT t.name, t.type FROM image_tags it "
            "JOIN tags t ON t.id = it.tag_id "
            "JOIN images i ON i.id = it.image_id WHERE i.filename = 'a.png'",
            (),
        )
        assert tag_rows == [("sunset", "General")]
    finally:
        db.close()

    # Idempotent
    report2 = migrate_pgvector.run(
        PASSWORD, SALT, db_path=lib, provider=fake_pg_provider
    )
    assert report2["images_in_target"] == 3


def test_003_skips_on_connection_failure(tmp_path):
    def broken_provider():
        raise ConnectionError("server down")

    report = migrate_pgvector.run(
        PASSWORD, SALT, db_path=str(tmp_path / "library.db"),
        provider=broken_provider,
    )
    assert report["skipped"]
    assert "server down" in report["reason"]


def test_004_verify_passes_and_catches_loss(tmp_path, legacy_db):
    lib = str(tmp_path / "library.db")
    migrate_listings.run(PASSWORD, SALT, db_path=lib, legacy_db_path=legacy_db)
    migrate_pgvector.run(PASSWORD, SALT, db_path=lib, provider=fake_pg_provider)

    report = verify_migration.run(
        PASSWORD, SALT, db_path=lib, legacy_db_path=legacy_db,
        pg_provider=fake_pg_provider,
    )
    assert report["ok"], report["problems"]
    assert report["internal"]["fk_violations"] == 0
    assert "entities:ent-2" in report["internal"]["dangling_parked"]

    # Simulate data loss → verification must fail.
    db = base.database.Database(lib, PASSWORD, SALT)
    db.execute("DELETE FROM media_items WHERE id = 'm-2'", ())
    db.close()
    report = verify_migration.run(
        PASSWORD, SALT, db_path=lib, legacy_db_path=legacy_db,
        pg_provider=fake_pg_provider,
    )
    assert not report["ok"]
    assert any("m-2" in p for p in report["problems"])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner_env(tmp_path, legacy_db, monkeypatch):
    """Sandbox every path constant the runner touches."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "listings.json.enc").write_bytes(b"enc")
    monkeypatch.setattr(backup_all, "LISTINGS_DB", Path(legacy_db))
    monkeypatch.setattr(backup_all, "SECRETS_DIR", secrets)
    monkeypatch.setattr(backup_all, "PRE_UNIFIED_DIR", tmp_path / "pre_unified")
    monkeypatch.setattr(backup_all, "ENV_FILE", tmp_path / "no.env")
    # Keep 004's pgvector leg offline-deterministic.
    monkeypatch.setattr(
        migrate_pgvector, "_postgres_provider",
        lambda: (_ for _ in ()).throw(ConnectionError("no server in tests")),
    )
    return {
        "db_path": str(tmp_path / "library.db"),
        "legacy_db_path": legacy_db,
        "state_file": tmp_path / "state.json",
    }


def test_runner_end_to_end_and_resume(runner_env):
    logs = []
    state = runner.run_all(
        PASSWORD, SALT, skip_postgres=True, log=logs.append, **runner_env
    )
    assert "000_backup_all" in state["completed"]
    assert "001_create_library_db" in state["completed"]
    assert "002_migrate_listings" in state["completed"]
    assert "003_migrate_pgvector" not in state["completed"]  # skipped
    assert state["completed"]["004_verify_migration"]["report"]["ok"]

    # Resume: already-done steps are skipped, verify runs again.
    logs2 = []
    runner.run_all(
        PASSWORD, SALT, skip_postgres=True, log=logs2.append, **runner_env
    )
    assert any("already done" in line for line in logs2)
    assert any("verification passed" in line for line in logs2)


def test_runner_gate_refuses_tampered_backup(runner_env):
    state = runner.run_all(
        PASSWORD, SALT, skip_postgres=True, log=lambda *_: None, **runner_env
    )
    # Corrupt the backup artifact, keep the manifest.
    backup_dir = Path(state["backup_manifest"]).parent
    (backup_dir / "listings_secure.db.bak").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="does not verify"):
        runner.run_all(
            PASSWORD, SALT, skip_postgres=True, log=lambda *_: None,
            **runner_env,
        )


def test_runner_fails_loudly_on_verification_problems(runner_env):
    runner.run_all(
        PASSWORD, SALT, skip_postgres=True, log=lambda *_: None, **runner_env
    )
    # Lose a migrated row, then re-run: 004 must abort the runner.
    db = base.database.Database(runner_env["db_path"], PASSWORD, SALT)
    db.execute("DELETE FROM entities WHERE id = 'ent-1'", ())
    db.close()
    with pytest.raises(RuntimeError, match="verification FAILED"):
        runner.run_all(
            PASSWORD, SALT, skip_postgres=True, log=lambda *_: None,
            **runner_env,
        )
