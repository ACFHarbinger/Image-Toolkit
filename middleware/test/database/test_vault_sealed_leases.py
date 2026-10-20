"""Tests for Issue #879 (Wave 0e W0-15): Vault in C++ core and sealed per-store leases.

Verifies:
1. Vault unlock (direct & keystore) and session handle lifecycle in C++ memory.
2. Master and store DEK protection (keys held in LockedSecret<32>, never exposed).
3. Sealed per-store lease token creation and verification.
4. Database opening via sealed leases (Database.from_lease, Database(path, lease)).
5. Database opening via active session handles (Database.from_session).
6. Store identity isolation (cloud_jobs vs library DEK separation).
7. TTL expiration enforcement.
8. Process PID binding enforcement.
9. AEAD tamper resistance (bit-flipping / corruption detection).
10. Transit key management and open_store_db integration.
"""

from __future__ import annotations

import os
import time

import backend
import pytest

from middleware.src.cloud.store.db import open_store_db, transaction
from middleware.src.core.vault_manager import VaultManager


@pytest.fixture(autouse=True)
def clean_vault_sessions():
    """Ensure all sessions and transit key overrides are cleared around each test."""
    backend.vault.clear_transit_key()
    backend.vault.lock_all()
    yield
    backend.vault.clear_transit_key()
    backend.vault.lock_all()


class TestVaultSessionLifecycle:
    def test_unlock_direct_and_lock(self):
        handle = backend.vault.unlock_direct("masterpass123", "testsalt456")
        assert handle.startswith("vses_")
        assert len(handle) == 5 + 32  # "vses_" + 32 hex chars
        assert backend.vault.is_unlocked(handle)
        assert handle in backend.vault.active_sessions()

        # Locking revokes session and wipes memory
        assert backend.vault.lock(handle) is True
        assert backend.vault.is_unlocked(handle) is False
        assert handle not in backend.vault.active_sessions()
        assert backend.vault.lock(handle) is False

    def test_lock_all(self):
        h1 = backend.vault.unlock_direct("pass1", "salt1")
        h2 = backend.vault.unlock_direct("pass2", "salt2")
        assert len(backend.vault.active_sessions()) == 2

        backend.vault.lock_all()
        assert len(backend.vault.active_sessions()) == 0
        assert backend.vault.is_unlocked(h1) is False
        assert backend.vault.is_unlocked(h2) is False

    def test_database_from_session(self, tmp_path):
        handle = backend.vault.unlock_direct("secretpass", "secretsalt")
        db_path = str(tmp_path / "session_test.db")

        # Open database using session handle
        db = backend.database.Database.from_session(db_path, handle, "library")
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT);", ())
        db.execute("INSERT INTO t (val) VALUES (?);", ("session_val",))
        rows = db.query("SELECT val FROM t;", ())
        assert rows == [("session_val",)]
        db.close()

        # Reopen with 3-arg constructor accepting session handle
        db2 = backend.database.Database(db_path, handle, "library")
        assert db2.query("SELECT val FROM t;", ()) == [("session_val",)]
        db2.close()

        # Once session is locked, from_session must fail
        backend.vault.lock(handle)
        with pytest.raises(RuntimeError, match="active session not found or locked"):
            backend.database.Database.from_session(db_path, handle, "library")


class TestSealedStoreLeases:
    def test_create_and_verify_lease(self):
        handle = backend.vault.unlock_direct("mypass", "mysalt")
        token = backend.vault.create_store_lease(
            handle,
            "cloud_jobs",
            pid=0,
            ttl_seconds=3600,
            supervisor_session="sup_sess_001",
        )
        assert token.startswith("itkl_v1_")

        # Verify metadata (key is NOT in returned dictionary)
        meta = backend.vault.verify_store_lease(token, expected_store="cloud_jobs")
        assert meta["store_name"] == "cloud_jobs"
        assert meta["supervisor_session"] == "sup_sess_001"
        assert meta["bound_pid"] == 0
        assert meta["expires_at"] > meta["created_at"]
        assert meta["is_expired"] is False
        assert meta["valid"] is True
        assert "key" not in meta
        assert "dek" not in meta

    def test_unlock_raw_keeps_the_keystore_bytes(self, tmp_path):
        raw = os.urandom(32)
        handle = backend.vault.unlock_raw(raw)
        db_path = str(tmp_path / "raw.db")
        db = backend.database.Database.from_session(db_path, handle, "library")
        db.execute("CREATE TABLE t (id INTEGER);", ())
        db.close()
        backend.vault.lock(handle)

        # Re-hashing the same bytes must not open this database.
        derived = backend.vault.unlock_direct(raw.hex(), "vault_salt")
        with pytest.raises(RuntimeError, match="cannot read database"):
            backend.database.Database.from_session(db_path, derived, "library")
        backend.vault.lock(derived)

        again = backend.vault.unlock_raw(raw)
        db2 = backend.database.Database.from_session(db_path, again, "library")
        assert db2.query("SELECT count(*) FROM t;", ()) == [(0,)]
        db2.close()

    def test_raw_store_lease(self):
        raw_key = os.urandom(32)
        token = backend.vault.create_raw_store_lease(
            "custom_store",
            raw_key,
            ttl_seconds=600,
        )
        assert token.startswith("itkl_v1_")
        meta = backend.vault.verify_store_lease(token, "custom_store")
        assert meta["store_name"] == "custom_store"
        assert meta["valid"] is True

    def test_store_name_empty_rejected(self):
        handle = backend.vault.unlock_direct("p", "s")
        with pytest.raises((RuntimeError, ValueError), match="store_name cannot be empty"):
            backend.vault.create_store_lease(handle, "")

    def test_open_database_with_lease(self, tmp_path):
        handle = backend.vault.unlock_direct("p", "s")
        lease = backend.vault.create_store_lease(handle, "cloud_jobs")
        db_path = str(tmp_path / "cloud_jobs.db")

        # Open via Database.from_lease
        db = backend.database.Database.from_lease(db_path, lease, expected_store="cloud_jobs")
        db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT);", ())
        db.execute("INSERT INTO jobs VALUES (?, ?);", ("job_1", "running"))
        db.close()

        # Reopen via 2-arg constructor Database(path, lease)
        db2 = backend.database.Database(db_path, lease)
        rows = db2.query("SELECT id, status FROM jobs;", ())
        assert rows == [("job_1", "running")]
        db2.close()

    def test_store_isolation_cloud_vs_library(self, tmp_path):
        handle = backend.vault.unlock_direct("master", "salt")
        lease_cloud = backend.vault.create_store_lease(handle, "cloud_jobs")
        lease_lib = backend.vault.create_store_lease(handle, "library")

        db_path = str(tmp_path / "isolated.db")

        # Create database with cloud_jobs lease
        db = backend.database.Database.from_lease(db_path, lease_cloud, "cloud_jobs")
        db.execute("CREATE TABLE t (x INT);", ())
        db.execute("INSERT INTO t VALUES (42);", ())
        db.close()

        # Opening with library lease must fail (wrong derived DEK)
        with pytest.raises(RuntimeError, match="cannot read database|HMAC check failed"):
            backend.database.Database.from_lease(db_path, lease_lib)

        # Opening with expected_store='library' on cloud_jobs lease fails store check
        with pytest.raises(RuntimeError, match="store lease mismatch: expected 'library', got 'cloud_jobs'"):
            backend.database.Database.from_lease(db_path, lease_cloud, expected_store="library")

    def test_ttl_expiration(self, tmp_path):
        handle = backend.vault.unlock_direct("p", "s")
        # 1-second TTL lease
        lease_exp = backend.vault.create_store_lease(handle, "cloud_jobs", ttl_seconds=1)
        time.sleep(1.2)

        meta = backend.vault.verify_store_lease(lease_exp)
        assert meta["is_expired"] is True
        assert meta["valid"] is False

        # Attempting to open database with expired lease must fail
        db_path = str(tmp_path / "exp.db")
        with pytest.raises(RuntimeError, match="has expired"):
            backend.database.Database.from_lease(db_path, lease_exp)

    def test_pid_binding(self, tmp_path):
        handle = backend.vault.unlock_direct("p", "s")
        current_pid = os.getpid()
        other_pid = current_pid + 99999

        # Bound to current PID -> succeeds
        good_lease = backend.vault.create_store_lease(handle, "cloud_jobs", pid=current_pid)
        meta_good = backend.vault.verify_store_lease(good_lease)
        assert meta_good["bound_pid"] == current_pid
        assert meta_good["pid_matches"] is True
        assert meta_good["valid"] is True

        db_path = str(tmp_path / "pid.db")
        db = backend.database.Database.from_lease(db_path, good_lease)
        db.close()

        # Bound to different PID -> fails
        bad_lease = backend.vault.create_store_lease(handle, "cloud_jobs", pid=other_pid)
        meta_bad = backend.vault.verify_store_lease(bad_lease)
        assert meta_bad["bound_pid"] == other_pid
        assert meta_bad["pid_matches"] is False
        assert meta_bad["valid"] is False

        with pytest.raises(RuntimeError, match="bound to PID"):
            backend.database.Database.from_lease(db_path, bad_lease)

    def test_tampering_rejected(self):
        handle = backend.vault.unlock_direct("p", "s")
        lease = backend.vault.create_store_lease(handle, "cloud_jobs")

        # Flip last characters
        tail = "XXXX" if not lease.endswith("XXXX") else "YYYY"
        tampered = lease[:-4] + tail

        with pytest.raises(RuntimeError, match="failed to decrypt lease token"):
            backend.vault.verify_store_lease(tampered)

        # Truncated token
        with pytest.raises(RuntimeError, match="too short or truncated|failed to decrypt"):
            backend.vault.verify_store_lease(lease[:20])

        # Missing prefix
        with pytest.raises(RuntimeError, match="invalid lease token format"):
            backend.vault.verify_store_lease("not_a_lease_token")

    def test_transit_key_isolation(self):
        # Set custom transit key 1
        key1 = b"\x11" * 32
        backend.vault.set_transit_key(key1)

        handle = backend.vault.unlock_direct("p", "s")
        lease = backend.vault.create_store_lease(handle, "cloud_jobs")

        # Verify succeeds with key1
        assert backend.vault.verify_store_lease(lease)["valid"] is True

        # Switch to transit key 2 -> verification must fail AEAD
        key2 = b"\x22" * 32
        backend.vault.set_transit_key(key2)
        with pytest.raises(RuntimeError, match="failed to decrypt lease token"):
            backend.vault.verify_store_lease(lease)


class TestCloudStoreAndVaultManagerIntegration:
    def test_open_store_db_with_lease(self, tmp_path):
        handle = backend.vault.unlock_direct("pwd", "salt")
        lease = backend.vault.create_store_lease(handle, "cloud_jobs")
        db_path = tmp_path / "cloud_jobs_integrated.db"

        # Open store db with lease=
        db = open_store_db(lease=lease, path=db_path)
        with transaction(db):
            db.execute(
                "INSERT INTO jobs (job_id, kind, state, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?);",
                ("job_abc", "extraction", "queued", "{}", 100.0, 100.0),
            )
        rows = db.query("SELECT job_id, kind, state FROM jobs WHERE job_id = ?;", ("job_abc",))
        assert rows == [("job_abc", "extraction", "queued")]
        db.close()

        # Reopen with secret=lease (positional backwards-compat)
        db2 = open_store_db(lease, "", path=db_path)
        rows2 = db2.query("SELECT job_id, kind, state FROM jobs WHERE job_id = ?;", ("job_abc",))
        assert rows2 == [("job_abc", "extraction", "queued")]
        db2.close()

    def test_vault_manager_create_store_lease(self, tmp_path):
        vm = VaultManager.create_guest_vault("test-user")
        session = vm.get_session_handle()
        assert session.startswith("vses_")

        lease = vm.create_store_lease("cloud_jobs")
        assert lease.startswith("itkl_v1_")

        meta = backend.vault.verify_store_lease(lease, "cloud_jobs")
        assert meta["store_name"] == "cloud_jobs"
        assert meta["valid"] is True

        vm.shutdown()
        assert not backend.vault.is_unlocked(session)
