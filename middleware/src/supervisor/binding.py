"""Production daemon-lease binding for the supervisor (#879).

The compatibility mint APIs still allow an unbound lease. This module is the
production path: it rejects a non-positive PID, a non-positive TTL, or a blank
supervisor session before the native minter is called.

Daemon transit keys stay mode 0600. That stops other users from reading them.
It does not stop other processes running as the same OS account. A same-account
process can still open the key file; isolating that case needs a file-descriptor
handoff, which is a separate design. Renewal and later store opens keep using
the key file, so this path does not unlink it.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Protocol

DAEMON_STORES = {
    "cloud_jobs": "cloud_jobs",
    "slideshow": "slideshow",
}


class BindingError(ValueError):
    """The production handoff refused to mint."""


class DaemonMinter(Protocol):
    def handoff_daemon_lease(
        self,
        store_name: str,
        daemon_name: str,
        data_dir: str | Path,
        pid: int = 0,
        ttl_seconds: int = 0,
        supervisor_session: str = "",
    ) -> str:
        """Mint one sealed lease. Production code calls this only after binding checks."""


def require_binding(*, pid: int, ttl_seconds: int, supervisor_session: str) -> None:
    """Reject unbound production parameters. Does not mint."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise BindingError("pid must be a positive process id")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise BindingError("ttl_seconds must be positive")
    if not isinstance(supervisor_session, str) or not supervisor_session.strip():
        raise BindingError("supervisor_session is required")


def renew_before(ttl_seconds: int) -> int:
    """Renew once half the TTL remains, and at least one second before expiry."""
    require_binding(pid=1, ttl_seconds=ttl_seconds, supervisor_session="renew")
    return max(1, ttl_seconds // 2)


class ProductionHandoff:
    """Mint only leases bound to a live PID, a positive TTL, and this supervisor session."""

    def __init__(self, vault: DaemonMinter) -> None:
        self._vault = vault

    def mint(
        self,
        *,
        store_name: str,
        daemon_name: str,
        data_dir: str | Path,
        pid: int,
        ttl_seconds: int,
        supervisor_session: str,
    ) -> str:
        require_binding(pid=pid, ttl_seconds=ttl_seconds, supervisor_session=supervisor_session)
        if not store_name or not daemon_name:
            raise BindingError("store_name and daemon_name are required")
        lease = self._vault.handoff_daemon_lease(
            store_name,
            daemon_name,
            data_dir,
            pid=pid,
            ttl_seconds=ttl_seconds,
            supervisor_session=supervisor_session,
        )
        if not isinstance(lease, str) or not lease or "\n" in lease or "\r" in lease:
            raise BindingError("daemon lease must be a single line")
        return lease


def session_path(data_dir: Path) -> Path:
    return data_dir / "supervisor" / "session"


def load_or_create_session(data_dir: Path) -> tuple[str, bool]:
    """Return ``(session_id, existed)``. A missing file is a new session, not a silent reuse."""
    path = session_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise BindingError("supervisor session file cannot be a symlink")
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing, True
    session = "sup_" + secrets.token_hex(16)
    _write_private(path, session + "\n")
    return session, False


def meta_path(data_dir: Path, name: str) -> Path:
    return data_dir / "supervisor" / f"{name}.lease-meta.json"


def save_lease_meta(data_dir: Path, name: str, *, pid: int, session: str, expires_at: float) -> None:
    payload = {"pid": pid, "session": session, "expires_at": expires_at}
    _write_private(meta_path(data_dir, name), json.dumps(payload) + "\n")


def load_lease_meta(data_dir: Path, name: str) -> dict[str, Any] | None:
    path = meta_path(data_dir, name)
    if path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def lease_still_valid(
    meta: dict[str, Any] | None,
    *,
    pid: int,
    session: str,
    now: float,
    ttl_seconds: int,
) -> bool:
    """A reattached child keeps its lease only when the session, PID, and expiry still match."""
    if meta is None:
        return False
    if meta.get("pid") != pid or meta.get("session") != session:
        return False
    expires_at = meta.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False
    return float(expires_at) - now > renew_before(ttl_seconds)


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
