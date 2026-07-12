"""Tests for backend/migrations/backup_all.py — the Phase DB backup gate."""

import json
from pathlib import Path

import pytest

from backend.migrations import backup_all


@pytest.fixture()
def fake_stores(tmp_path, monkeypatch):
    """Point every source/destination constant at tmp_path."""
    listings = tmp_path / "listings_secure.db"
    listings.write_bytes(b"sqlcipher-bytes-placeholder")

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "listings.json.enc").write_bytes(b"enc-listings")
    (secrets / "entities.json.enc").write_bytes(b"enc-entities")

    dest_root = tmp_path / "pre_unified"

    monkeypatch.setattr(backup_all, "LISTINGS_DB", listings)
    monkeypatch.setattr(backup_all, "SECRETS_DIR", secrets)
    monkeypatch.setattr(backup_all, "PRE_UNIFIED_DIR", dest_root)
    monkeypatch.setattr(backup_all, "ENV_FILE", tmp_path / "no-vars.env")
    return tmp_path, dest_root


def test_backup_copies_all_artifacts(fake_stores):
    tmp_path, dest_root = fake_stores
    manifest = backup_all.run_backup()

    backup_dir = Path(manifest["backup_dir"])
    assert backup_dir.parent == dest_root
    assert (backup_dir / "listings_secure.db.bak").read_bytes() == (
        b"sqlcipher-bytes-placeholder"
    )
    assert (backup_dir / "listings.json.enc").exists()
    assert (backup_dir / "entities.json.enc").exists()

    names = set(manifest["artifacts"])
    assert names == {
        "listings_secure.db.bak",
        "listings.json.enc",
        "entities.json.enc",
    }
    # Postgres skip is a warning, never an error
    assert any("DB_NAME" in w or "pg_dump" in w for w in manifest["warnings"])

    on_disk = json.loads((backup_dir / backup_all.MANIFEST_NAME).read_text())
    assert on_disk["artifacts"] == manifest["artifacts"]


def test_backup_refuses_empty(fake_stores, monkeypatch):
    tmp_path, dest_root = fake_stores
    monkeypatch.setattr(backup_all, "LISTINGS_DB", tmp_path / "missing.db")
    monkeypatch.setattr(backup_all, "SECRETS_DIR", tmp_path / "missing-secrets")
    with pytest.raises(RuntimeError, match="no artifacts"):
        backup_all.run_backup()
    # No manifest may be left behind
    assert backup_all.find_latest_manifest(dest_root) is None


def test_verify_manifest_detects_tampering(fake_stores):
    _, dest_root = fake_stores
    manifest = backup_all.run_backup()
    manifest_path = Path(manifest["backup_dir"]) / backup_all.MANIFEST_NAME

    assert backup_all.verify_manifest(manifest_path) == []

    (Path(manifest["backup_dir"]) / "listings_secure.db.bak").write_bytes(
        b"corrupted"
    )
    problems = backup_all.verify_manifest(manifest_path)
    assert problems and "checksum mismatch" in problems[0]


def test_find_latest_manifest_orders_by_timestamp(fake_stores):
    _, dest_root = fake_stores
    first = backup_all.run_backup(dest_root / "20200101T000000Z")
    second = backup_all.run_backup(dest_root / "20300101T000000Z")
    latest = backup_all.find_latest_manifest(dest_root)
    assert latest is not None
    assert str(latest.parent) == second["backup_dir"]
    assert str(latest.parent) != first["backup_dir"]
