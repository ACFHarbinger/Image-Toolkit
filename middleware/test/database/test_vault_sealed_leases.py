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
def clean_vault_sessions(tmp_path, monkeypatch):
    """Ensure all sessions and transit key overrides are cleared around each test."""
    monkeypatch.setenv("IMAGE_TOOLKIT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("IMAGE_TOOLKIT_DIR", str(tmp_path))
    backend.vault.rotate_transit_key()
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

    def test_mint_daemon_lease_and_permissions(self, tmp_path):
        handle = backend.vault.unlock_direct("mypass", "mysalt")
        data_dir = tmp_path / "data"
        current_pid = os.getpid()

        lease = backend.vault.mint_daemon_lease(
            handle,
            "cloud_jobs",
            "cloud_jobs",
            str(data_dir),
            pid=current_pid,
            ttl_seconds=3600,
            supervisor_session="sup_001",
        )
        assert lease.startswith("itkl_v1_")

        key_file = data_dir / "supervisor" / "keys" / "cloud_jobs.key"
        assert key_file.exists()
        import stat
        file_mode = stat.S_IMODE(os.stat(key_file).st_mode)
        assert file_mode == 0o600

        # Verification with daemon key path
        meta = backend.vault.verify_store_lease(
            lease,
            expected_store="cloud_jobs",
            expected_supervisor_session="sup_001",
            daemon_key_path=str(key_file),
        )
        assert meta["store_name"] == "cloud_jobs"
        assert meta["supervisor_session"] == "sup_001"
        assert meta["supervisor_matches"] is True
        assert meta["bound_pid"] == current_pid
        assert meta["pid_matches"] is True
        assert meta["valid"] is True

        # Open DB with daemon key path
        db_path = str(tmp_path / "daemon_test.db")
        db = backend.database.Database.from_lease(
            db_path,
            lease,
            expected_store="cloud_jobs",
            expected_supervisor_session="sup_001",
            daemon_key_path=str(key_file),
        )
        db.execute("CREATE TABLE t (x TEXT);", ())
        db.execute("INSERT INTO t VALUES ('ok');", ())
        assert db.query("SELECT x FROM t;", ()) == [("ok",)]
        db.close()

    def test_cross_daemon_key_isolation(self, tmp_path):
        handle = backend.vault.unlock_direct("mypass", "mysalt")
        data_dir = tmp_path / "data"

        lease_cloud = backend.vault.mint_daemon_lease(
            handle, "cloud_jobs", "cloud_jobs", str(data_dir), ttl_seconds=3600
        )
        lease_slide = backend.vault.mint_daemon_lease(
            handle, "slideshow", "slideshow", str(data_dir), ttl_seconds=3600
        )

        cloud_key = str(data_dir / "supervisor" / "keys" / "cloud_jobs.key")
        slide_key = str(data_dir / "supervisor" / "keys" / "slideshow.key")

        # Cloud jobs lease unseals with cloud_key
        assert backend.vault.verify_store_lease(lease_cloud, daemon_key_path=cloud_key)["valid"] is True

        # Slideshow lease unseals with slide_key
        assert backend.vault.verify_store_lease(lease_slide, daemon_key_path=slide_key)["valid"] is True

        # Cross-daemon unseal must fail AEAD decryption (different per-daemon transit key)
        with pytest.raises(RuntimeError, match="failed to decrypt lease token"):
            backend.vault.verify_store_lease(lease_cloud, daemon_key_path=slide_key)

        with pytest.raises(RuntimeError, match="failed to decrypt lease token"):
            backend.vault.verify_store_lease(lease_slide, daemon_key_path=cloud_key)

    def test_insecure_key_permissions_rejected(self, tmp_path):
        handle = backend.vault.unlock_direct("mypass", "mysalt")
        data_dir = tmp_path / "data"

        lease = backend.vault.mint_daemon_lease(
            handle, "cloud_jobs", "cloud_jobs", str(data_dir)
        )
        key_file = data_dir / "supervisor" / "keys" / "cloud_jobs.key"

        # Make permissions insecure (0644 readable by other users)
        os.chmod(key_file, 0o644)

        with pytest.raises(RuntimeError, match="insecure permissions"):
            backend.vault.verify_store_lease(lease, daemon_key_path=str(key_file))

    def test_supervisor_session_binding(self, tmp_path):
        handle = backend.vault.unlock_direct("p", "s")
        data_dir = tmp_path / "data"
        lease = backend.vault.mint_daemon_lease(
            handle, "cloud_jobs", "cloud_jobs", str(data_dir), supervisor_session="session_A"
        )
        key_file = str(data_dir / "supervisor" / "keys" / "cloud_jobs.key")

        # Matching expected supervisor session succeeds
        meta = backend.vault.verify_store_lease(
            lease,
            expected_store="cloud_jobs",
            expected_supervisor_session="session_A",
            daemon_key_path=key_file,
        )
        assert meta["supervisor_matches"] is True
        assert meta["valid"] is True

        # Mismatched expected supervisor session fails verify
        meta_mismatch = backend.vault.verify_store_lease(
            lease,
            expected_store="cloud_jobs",
            expected_supervisor_session="session_B",
            daemon_key_path=key_file,
        )
        assert meta_mismatch["supervisor_matches"] is False
        assert meta_mismatch["valid"] is False

        # Database.from_lease with mismatched session raises error
        db_path = str(tmp_path / "sup_test.db")
        with pytest.raises(RuntimeError, match="supervisor session mismatch"):
            backend.database.Database.from_lease(
                db_path,
                lease,
                expected_store="cloud_jobs",
                expected_supervisor_session="session_B",
                daemon_key_path=key_file,
            )

        # Environment variable ITK_SUPERVISOR_SESSION mismatch
        os.environ["ITK_SUPERVISOR_SESSION"] = "session_WRONG"
        try:
            with pytest.raises(RuntimeError, match="supervisor session mismatch with environment"):
                backend.database.Database.from_lease(
                    db_path,
                    lease,
                    expected_store="cloud_jobs",
                    daemon_key_path=key_file,
                )
        finally:
            os.environ.pop("ITK_SUPERVISOR_SESSION", None)

    def test_genuine_separate_daemon_process(self, tmp_path):
        import subprocess
        import sys

        session = backend.vault.unlock_direct("daemon_pass", "daemon_salt")
        data_dir = tmp_path / "app_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "cloud_jobs.db"
        sup_session = "sup_test_sess_001"

        worker_script = f"""
import os
import sys
import backend

db_path = {repr(str(db_path))}
data_dir = {repr(str(data_dir))}
sup_session = {repr(sup_session)}
daemon_name = "cloud_jobs"

os.environ["IMAGE_TOOLKIT_DATA_DIR"] = data_dir
os.environ["ITK_DAEMON_NAME"] = daemon_name
os.environ["ITK_SUPERVISOR_SESSION"] = sup_session

# Report worker PID to parent
sys.stdout.write(f"{{os.getpid()}}\\n")
sys.stdout.flush()

# Read lease from parent via stdin
lease = sys.stdin.readline().strip()

try:
    db = backend.database.Database.from_lease(
        db_path,
        lease,
        expected_store="cloud_jobs",
        expected_supervisor_session=sup_session,
    )
    db.execute("CREATE TABLE IF NOT EXISTS daemon_jobs (id TEXT PRIMARY KEY, worker_pid INT);", ())
    db.execute("INSERT INTO daemon_jobs VALUES (?, ?);", ("job_daemon_1", os.getpid()))
    db.close()
    sys.exit(0)
except Exception as e:
    sys.stderr.write(f"DAEMON ERROR: {{e}}\\n")
    sys.exit(1)
"""
        from pathlib import Path
        repo_root = str(Path(__file__).resolve().parents[3])
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join([repo_root, existing]) if existing else repo_root

        proc = subprocess.Popen(
            [sys.executable, "-c", worker_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(tmp_path),
            env=env,
        )

        child_pid_str = proc.stdout.readline().strip()
        child_pid = int(child_pid_str)
        assert child_pid > 0

        # Parent mints lease bound to child PID
        lease = backend.vault.mint_daemon_lease(
            session,
            "cloud_jobs",
            "cloud_jobs",
            str(data_dir),
            pid=child_pid,
            ttl_seconds=300,
            supervisor_session=sup_session,
        )

        # Parent attempting to unseal child's lease in parent process must fail PID check
        key_file = str(data_dir / "supervisor" / "keys" / "cloud_jobs.key")
        with pytest.raises(RuntimeError, match="bound to PID"):
            backend.database.Database.from_lease(
                str(db_path),
                lease,
                expected_store="cloud_jobs",
                daemon_key_path=key_file,
            )

        # Send lease to child process
        proc.stdin.write(lease + "\n")
        proc.stdin.flush()

        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, f"Child daemon failed with stderr: {stderr}"

        # Verify database contents from parent using active session
        db_parent = backend.database.Database.from_session(str(db_path), session, "cloud_jobs")
        rows = db_parent.query("SELECT id, worker_pid FROM daemon_jobs;", ())
        assert rows == [("job_daemon_1", child_pid)]
        db_parent.close()
        backend.vault.lock(session)

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
        backend.vault.rotate_transit_key()
        handle = backend.vault.unlock_direct("p", "s")
        lease = backend.vault.create_store_lease(handle, "cloud_jobs")

        # Verify succeeds with current transit key
        assert backend.vault.verify_store_lease(lease)["valid"] is True

        # Rotate transit key in C++ memory -> verification must fail AEAD
        backend.vault.rotate_transit_key()
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

    def test_vault_manager_handoff_daemon_lease(self, tmp_path):
        vm = VaultManager.create_guest_vault("test-user")
        data_dir = tmp_path / "vm_data"

        lease = vm.handoff_daemon_lease(
            store_name="cloud_jobs",
            daemon_name="cloud_jobs",
            data_dir=data_dir,
            supervisor_session="sup_vm_001",
        )
        assert lease.startswith("itkl_v1_")
        key_file = data_dir / "supervisor" / "keys" / "cloud_jobs.key"
        assert key_file.exists()

        db_path = tmp_path / "vm_cloud_jobs.db"
        db = open_store_db(
            lease=lease,
            path=db_path,
            expected_supervisor_session="sup_vm_001",
            daemon_key_path=str(key_file),
        )
        with transaction(db):
            db.execute(
                "INSERT INTO jobs (job_id, kind, state, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?);",
                ("job_vm_1", "extraction", "queued", "{}", 1.0, 1.0),
            )
        rows = db.query("SELECT job_id FROM jobs WHERE job_id = ?;", ("job_vm_1",))
        assert rows == [("job_vm_1",)]
        db.close()

        vm.shutdown()


def test_repeated_mint_preserves_other_store_leases(tmp_path):
    session = backend.vault.unlock_direct("test", "test-salt")
    first = backend.vault.mint_daemon_lease(session, "cloud_jobs", "worker", str(tmp_path))
    second = backend.vault.mint_daemon_lease(session, "library", "worker", str(tmp_path))
    key = str(tmp_path / "supervisor/keys/worker.key")
    assert backend.vault.verify_store_lease(first, daemon_key_path=key)["valid"]
    assert backend.vault.verify_store_lease(second, daemon_key_path=key)["valid"]


def test_daemon_name_cannot_escape_key_directory(tmp_path):
    session = backend.vault.unlock_direct("test", "test-salt")
    with pytest.raises((ValueError, RuntimeError)):
        backend.vault.mint_daemon_lease(session, "cloud_jobs", "../escape", str(tmp_path))
    assert not (tmp_path / "supervisor/escape.key").exists()


def test_daemon_key_symlink_is_rejected(tmp_path):
    session = backend.vault.unlock_direct("test", "test-salt")
    lease = backend.vault.mint_daemon_lease(session, "cloud_jobs", "worker", str(tmp_path))
    alias = tmp_path / "alias.key"
    alias.symlink_to(tmp_path / "supervisor/keys/worker.key")
    with pytest.raises(RuntimeError):
        backend.vault.verify_store_lease(lease, daemon_key_path=str(alias))


def test_configured_daemon_cannot_fall_back_to_legacy_transit_key(tmp_path, monkeypatch):
    session = backend.vault.unlock_direct("test", "test-salt")
    lease = backend.vault.create_store_lease(session, "cloud_jobs")
    monkeypatch.setenv("ITK_DAEMON_NAME", "missing-worker")
    with pytest.raises(RuntimeError):
        backend.vault.verify_store_lease(lease)


def test_metadata_checks_supervisor_environment(monkeypatch):
    session = backend.vault.unlock_direct("test", "test-salt")
    lease = backend.vault.create_store_lease(session, "cloud_jobs", supervisor_session="old")
    monkeypatch.setenv("ITK_SUPERVISOR_SESSION", "new")
    assert not backend.vault.verify_store_lease(lease)["valid"]
