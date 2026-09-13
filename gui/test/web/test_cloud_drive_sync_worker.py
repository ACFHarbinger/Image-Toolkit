"""Tests for the unified cloud-drive sync worker (ui-arch-41 / #563, R2.a).

Runs ``CloudDriveSyncWorker`` directly on the test thread with faked
backend managers — no network, no threads. Covers provider dispatch,
credential plumbing per provider, the finished-payload contract, and
cooperative stop.
"""

from __future__ import annotations

import pytest

import gui.src.helpers.web.cloud.cloud_drive_sync_worker as sync_mod
from gui.src.helpers.web.cloud.cloud_drive_sync_worker import CloudDriveSyncWorker


class _FakeManager:
    """Stand-in backend sync manager capturing constructor kwargs."""

    last_kwargs = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self._is_running = True
        self.result = (True, "done")
        self.executed = False

    def execute_sync(self):
        self.executed = True
        return self.result


@pytest.fixture
def fake_backends(monkeypatch):
    _FakeManager.last_kwargs = None
    made = {}

    def _factory(name):
        def _make(**kwargs):
            manager = _FakeManager(**kwargs)
            manager.backend = name
            made[name] = manager
            return manager

        return _make

    monkeypatch.setattr(sync_mod, "DropboxDriveSync", _factory("dropbox"))
    monkeypatch.setattr(sync_mod, "OneDriveSync", _factory("onedrive"))
    monkeypatch.setattr(sync_mod, "GoogleDriveSync", _factory("google"))
    return made


def _run(worker):
    # Direct synchronous run on the test thread (no pool); QRunnable
    # workers carry no deleteLater — plain GC applies.
    statuses = []
    finished = []
    worker.signals.status.connect(statuses.append)
    worker.signals.finished.connect(finished.append)
    worker.run()
    return statuses, finished


def _base_args(**overrides):
    args = {
        "auth_config": {"access_token": "tok", "client_id": "cid"},
        "local_path": "/tmp/local",
        "remote_path": "remote",
        "dry_run": True,
    }
    args.update(overrides)
    return args


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="Unknown sync provider"):
        CloudDriveSyncWorker("ftp", {}, "/a", "/b", True)


def test_dropbox_success_payload_and_banner(fake_backends):
    worker = CloudDriveSyncWorker("dropbox", **_base_args())
    statuses, finished = _run(worker)
    assert finished == [(True, "done", True)]
    assert any("Dropbox Sync Initiated" in line for line in statuses)
    assert any("DRY RUN" in line for line in statuses)
    manager = fake_backends["dropbox"]
    assert manager.last_kwargs["access_token"] == "tok"
    assert manager.executed


def test_onedrive_credential_key(fake_backends):
    worker = CloudDriveSyncWorker("onedrive", **_base_args(dry_run=False))
    _, finished = _run(worker)
    assert finished == [(True, "done", False)]
    assert fake_backends["onedrive"].last_kwargs["client_id"] == "cid"
    assert "access_token" not in fake_backends["onedrive"].last_kwargs


def test_google_personal_account_kwargs(fake_backends):
    auth = {
        "mode": "personal_account",
        "client_secrets_data": {"x": 1},
        "token_file": "/tmp/token.json",
    }
    worker = CloudDriveSyncWorker("google", **_base_args(auth_config=auth))
    statuses, finished = _run(worker)
    assert finished == [(True, "done", True)]
    kwargs = fake_backends["google"].last_kwargs
    assert kwargs["client_secrets_data"] == {"x": 1}
    assert kwargs["token_file"] == "/tmp/token.json"
    assert kwargs["service_account_data"] is None
    assert any("Authentication Mode: PERSONAL_ACCOUNT" in line for line in statuses)


def test_google_unsupported_mode_fails(fake_backends):
    worker = CloudDriveSyncWorker("google", **_base_args(auth_config={"mode": "weird"}))
    statuses, finished = _run(worker)
    assert finished == [(False, "Critical error: Unsupported authentication mode: weird", True)]
    assert any("ERROR" in line for line in statuses)


def test_precancelled_worker_emits_none(fake_backends):
    worker = CloudDriveSyncWorker("dropbox", **_base_args())
    worker.cancel()
    _, finished = _run(worker)
    assert finished == [None]


def test_stop_before_execute_skips_backend(fake_backends):
    auth = {"mode": "personal_account", "client_secrets_data": {}, "token_file": "t"}
    worker = CloudDriveSyncWorker("google", **_base_args(auth_config=auth))
    # Stop before execute: manager is built but never runs.
    worker.stop()
    _, finished = _run(worker)
    assert finished == [(False, "Cancelled by user.", True)]
    assert fake_backends["google"].executed is False


def test_stop_propagates_to_running_manager(fake_backends):
    worker = CloudDriveSyncWorker("dropbox", **_base_args())
    worker.sync_manager = _FakeManager()
    worker.stop()
    assert worker.sync_manager._is_running is False
