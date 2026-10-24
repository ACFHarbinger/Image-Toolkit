"""Production supervisor binding for sealed daemon leases (#879).

These tests use a fake minter and genuine child processes. They do not open
the native vault and they do not touch the user library.
"""

from __future__ import annotations

import os
import signal
import threading
import time
from pathlib import Path

import pytest

from middleware.src.supervisor.binding import (
    BindingError,
    ProductionHandoff,
    load_or_create_session,
    session_path,
)
from middleware.src.supervisor.children import (
    CHILD_NAMES,
    CLOUD_JOBS,
    SIDECAR,
    SLIDESHOW,
    heartbeat,
    is_pid_alive,
)
from middleware.src.supervisor.supervisor import Supervisor


class FakeVault:
    """Records production mint calls. A configured daemon name fails closed."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()
        self.calls: list[dict[str, object]] = []
        self._mu = threading.Lock()

    def handoff_daemon_lease(
        self,
        store_name: str,
        daemon_name: str,
        data_dir: str | Path,
        pid: int = 0,
        ttl_seconds: int = 0,
        supervisor_session: str = "",
    ) -> str:
        if daemon_name in self.fail:
            raise RuntimeError("mint failed")
        with self._mu:
            lease = f"itkl_v1_{daemon_name}_{pid}_{len(self.calls)}"
            self.calls.append(
                {
                    "store": store_name,
                    "daemon": daemon_name,
                    "pid": pid,
                    "ttl": ttl_seconds,
                    "session": supervisor_session,
                    "lease": lease,
                    "mono": time.monotonic(),
                }
            )
        return lease

    def snapshot(self) -> list[dict[str, object]]:
        with self._mu:
            return list(self.calls)


def _wait_for(predicate, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("condition not met before timeout")


def _proc_blob(pid: int) -> str:
    chunks: list[str] = []
    for name in ("cmdline", "environ"):
        try:
            raw = Path(f"/proc/{pid}/{name}").read_bytes()
        except OSError:
            continue
        chunks.append(raw.replace(b"\x00", b"\n").decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _supervisor_files(data_dir: Path) -> str:
    root = data_dir / "supervisor"
    parts: list[str] = []
    if not root.exists():
        return ""
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _reap_pidfiles(data_dir: Path) -> None:
    root = data_dir / "supervisor"
    for name in CHILD_NAMES:
        path = root / f"{name}.pid"
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if is_pid_alive(pid):
            os.kill(pid, signal.SIGKILL)


def _start(tmp_path: Path, vault: FakeVault, ttl: int = 30) -> Supervisor:
    sup = Supervisor(
        tmp_path,
        vault=vault,
        poll_interval_s=0.05,
        lease_ttl_seconds=ttl,
    )
    sup.start()
    sup.wait_until_ready()
    return sup


def test_production_handoff_rejects_pid_ttl_and_session(tmp_path: Path) -> None:
    vault = FakeVault()

    def refuse(*_args, **_kwargs):
        raise AssertionError("minter must not be called")

    vault.handoff_daemon_lease = refuse  # type: ignore[method-assign]
    handoff = ProductionHandoff(vault)
    rejected = [
        {"pid": 0, "ttl_seconds": 30, "supervisor_session": "sup_ok"},
        {"pid": -4, "ttl_seconds": 30, "supervisor_session": "sup_ok"},
        {"pid": True, "ttl_seconds": 30, "supervisor_session": "sup_ok"},
        {"pid": os.getpid(), "ttl_seconds": 0, "supervisor_session": "sup_ok"},
        {"pid": os.getpid(), "ttl_seconds": -2, "supervisor_session": "sup_ok"},
        {"pid": os.getpid(), "ttl_seconds": True, "supervisor_session": "sup_ok"},
        {"pid": os.getpid(), "ttl_seconds": 30, "supervisor_session": ""},
        {"pid": os.getpid(), "ttl_seconds": 30, "supervisor_session": " \n\t"},
    ]
    for kwargs in rejected:
        with pytest.raises(BindingError):
            handoff.mint(
                store_name="cloud_jobs",
                daemon_name="cloud_jobs",
                data_dir=tmp_path,
                **kwargs,
            )
    assert vault.snapshot() == []


def test_blank_session_file_is_a_new_session(tmp_path: Path) -> None:
    session, existed = load_or_create_session(tmp_path)
    assert existed is False
    assert session.startswith("sup_")
    path = session_path(tmp_path)
    assert (path.stat().st_mode & 0o777) == 0o600
    again, existed = load_or_create_session(tmp_path)
    assert existed is True
    assert again == session

    path.write_text("\n", encoding="utf-8")
    fresh, existed = load_or_create_session(tmp_path)
    assert existed is False
    assert fresh != session

    path.unlink()
    path.symlink_to(tmp_path / "not-the-session")
    with pytest.raises(BindingError, match="symlink"):
        load_or_create_session(tmp_path)


def test_cross_store_mint_keeps_daemon_key_file(tmp_path: Path) -> None:
    key = tmp_path / "supervisor" / "keys" / "worker.key"
    key.parent.mkdir(parents=True)
    key.write_bytes(b"k" * 32)
    os.chmod(key, 0o600)
    vault = FakeVault()
    handoff = ProductionHandoff(vault)
    for store in ("cloud_jobs", "library"):
        handoff.mint(
            store_name=store,
            daemon_name="worker",
            data_dir=tmp_path,
            pid=os.getpid(),
            ttl_seconds=30,
            supervisor_session="sup_shared",
        )
    assert key.read_bytes() == b"k" * 32
    calls = vault.snapshot()
    assert [call["store"] for call in calls] == ["cloud_jobs", "library"]
    assert {call["daemon"] for call in calls} == {"worker"}
    assert all("\n" not in str(call["lease"]) for call in calls)


def test_child_stays_unready_until_lease_and_lease_stays_off_argv(tmp_path: Path) -> None:
    vault = FakeVault()
    hold = threading.Event()
    entered = threading.Event()
    real = vault.handoff_daemon_lease

    def held(store_name, daemon_name, data_dir, pid=0, ttl_seconds=0, supervisor_session=""):
        lease = real(
            store_name,
            daemon_name,
            data_dir,
            pid=pid,
            ttl_seconds=ttl_seconds,
            supervisor_session=supervisor_session,
        )
        if daemon_name == CLOUD_JOBS:
            entered.set()
            assert hold.wait(timeout=5)
        return lease

    vault.handoff_daemon_lease = held  # type: ignore[method-assign]
    sup = Supervisor(tmp_path, vault=vault, poll_interval_s=0.05, lease_ttl_seconds=30)
    errors: list[BaseException] = []

    def _run() -> None:
        try:
            sup.start()
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    thread = threading.Thread(target=_run)
    thread.start()
    try:
        assert entered.wait(timeout=5)
        pid = int((tmp_path / "supervisor" / f"{CLOUD_JOBS}.pid").read_text(encoding="utf-8"))
        assert heartbeat(tmp_path, CLOUD_JOBS) is None
        blob = _proc_blob(pid)
        assert "itkl_v1_" not in blob
        assert "IMAGE_TOOLKIT_WAIT_LEASE=1" in blob
        assert "ITK_SUPERVISOR_SESSION=sup_" in blob
        assert "itkl_v1_" not in _supervisor_files(tmp_path)
    finally:
        hold.set()
        thread.join(timeout=5)
    assert errors == []
    assert not thread.is_alive()
    try:
        sup.wait_until_ready()
        beat = heartbeat(tmp_path, CLOUD_JOBS)
        assert beat is not None
        assert beat["pid"] == sup.children[CLOUD_JOBS].pid
        assert "itkl_v1_" not in str(beat)
    finally:
        sup.stop()
        _reap_pidfiles(tmp_path)


def test_bound_daemons_receive_leases_sidecar_does_not(tmp_path: Path) -> None:
    vault = FakeVault()
    sup = _start(tmp_path, vault)
    try:
        calls = vault.snapshot()
        assert {call["daemon"] for call in calls} == {CLOUD_JOBS, SLIDESHOW}
        kids = sup.children
        for name in (CLOUD_JOBS, SLIDESHOW):
            pid = kids[name].pid
            matched = [call for call in calls if call["daemon"] == name]
            assert matched[0]["pid"] == pid
            assert str(matched[0]["session"]).startswith("sup_")
            assert "itkl_v1_" not in _proc_blob(pid)
            beat = heartbeat(tmp_path, name)
            assert beat is not None
            assert "itkl_v1_" not in str(beat)
        assert "itkl_v1_" not in _supervisor_files(tmp_path)
        sidecar_env = _proc_blob(kids[SIDECAR].pid)
        assert "IMAGE_TOOLKIT_WAIT_LEASE" not in sidecar_env
    finally:
        sup.stop()
        _reap_pidfiles(tmp_path)


def test_mint_failure_leaves_no_live_pid(tmp_path: Path) -> None:
    vault = FakeVault(fail={CLOUD_JOBS})
    sup = Supervisor(tmp_path, vault=vault, poll_interval_s=0.05, lease_ttl_seconds=30)
    try:
        with pytest.raises(RuntimeError, match="mint failed"):
            sup.start()
    finally:
        sup.stop()
        _reap_pidfiles(tmp_path)
    for name in CHILD_NAMES:
        path = tmp_path / "supervisor" / f"{name}.pid"
        if not path.exists():
            continue
        pid = int(path.read_text(encoding="utf-8"))
        assert not is_pid_alive(pid)
    assert [call["daemon"] for call in vault.snapshot()] == []


def test_restart_mints_for_new_pid_same_session(tmp_path: Path) -> None:
    vault = FakeVault()
    sup = _start(tmp_path, vault, ttl=30)
    try:
        old_pid = sup.children[CLOUD_JOBS].pid
        session = vault.snapshot()[0]["session"]
        before = len(vault.snapshot())
        os.kill(old_pid, signal.SIGKILL)
        _wait_for(lambda: sup.children[CLOUD_JOBS].pid != old_pid)
        new_pid = sup.children[CLOUD_JOBS].pid
        _wait_for(lambda: any(call["daemon"] == CLOUD_JOBS and call["pid"] == new_pid for call in vault.snapshot()))
        minted = [call for call in vault.snapshot() if call["daemon"] == CLOUD_JOBS and call["pid"] == new_pid]
        assert minted
        assert minted[0]["session"] == session
        assert len(vault.snapshot()) > before
        assert not is_pid_alive(old_pid)
        assert is_pid_alive(new_pid)
    finally:
        sup.stop()
        _reap_pidfiles(tmp_path)


def test_renewal_mints_again_before_ttl(tmp_path: Path) -> None:
    ttl = 4
    vault = FakeVault()
    sup = _start(tmp_path, vault, ttl=ttl)
    try:
        first = next(call for call in vault.snapshot() if call["daemon"] == CLOUD_JOBS)
        pid = first["pid"]

        def _renewed() -> bool:
            return sum(1 for call in vault.snapshot() if call["daemon"] == CLOUD_JOBS and call["pid"] == pid) >= 2

        _wait_for(_renewed, timeout_s=6)
        second = [call for call in vault.snapshot() if call["daemon"] == CLOUD_JOBS and call["pid"] == pid][1]
        assert float(second["mono"]) < float(first["mono"]) + ttl
        assert second["session"] == first["session"]
        assert sup.children[CLOUD_JOBS].pid == pid
    finally:
        sup.stop()
        _reap_pidfiles(tmp_path)


def test_reattach_same_session_and_pid_does_not_mint(tmp_path: Path) -> None:
    vault = FakeVault()
    sup = _start(tmp_path, vault, ttl=60)
    pids = {name: sup.children[name].pid for name in CHILD_NAMES}
    calls = len(vault.snapshot())
    sup.stop(reap_children=False)
    again = Supervisor(tmp_path, vault=vault, poll_interval_s=0.05, lease_ttl_seconds=60)
    try:
        again.start()
        again.wait_until_ready()
        assert {name: again.children[name].pid for name in CHILD_NAMES} == pids
        assert len(vault.snapshot()) == calls
        assert all(is_pid_alive(pid) for pid in pids.values())
    finally:
        again.stop()
        _reap_pidfiles(tmp_path)


def test_missing_session_file_respawns_with_new_session(tmp_path: Path) -> None:
    vault = FakeVault()
    sup = _start(tmp_path, vault, ttl=60)
    old = {name: sup.children[name].pid for name in (CLOUD_JOBS, SLIDESHOW)}
    old_session = str(vault.snapshot()[0]["session"])
    sup.stop(reap_children=False)
    session_path(tmp_path).unlink()
    again = Supervisor(tmp_path, vault=vault, poll_interval_s=0.05, lease_ttl_seconds=60)
    try:
        again.start()
        again.wait_until_ready()
        fresh = [
            call
            for call in vault.snapshot()
            if call["pid"] in {again.children[CLOUD_JOBS].pid, again.children[SLIDESHOW].pid}
        ]
        assert fresh
        assert {str(call["session"]) for call in fresh} != {old_session}
        for name, pid in old.items():
            assert again.children[name].pid != pid
            assert not is_pid_alive(pid)
    finally:
        again.stop()
        _reap_pidfiles(tmp_path)
