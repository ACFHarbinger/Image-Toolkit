"""Local Directory Sync worker — bidirectional ``~/.image-toolkit/`` ↔ remote.

Runs on a GC-guarded ``QThread`` (mirrors ``google_drive_sync_worker.py``).
Pure diff/conflict logic lives in :class:`LocalDirSyncEngine` so it can be
unit-tested without a Qt event loop or real cloud credentials.
"""

from __future__ import annotations

import gc
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

# ---------------------------------------------------------------------------
# Security: default exclude patterns for files that must not leave the machine.
# Path leak risk: logs/traces carry absolute host paths.
# Vault key material: AES-256-GCM encrypted but we don't send key files.
# ---------------------------------------------------------------------------
DEFAULT_EXCLUDES: Tuple[str, ...] = (
    # --- Key material — must never leave the machine ---
    "*.vault",
    "*.p12",
    "*.pfx",
    "*.pem",
    "*.key",
    ".keystore",
    "secrets/",
    "cryptography/",  # ~/.image-toolkit/cryptography holds key material
    # --- Databases — live SQLCipher / SQLite stores. Byte-syncing these
    #     across devices with last-write-wins corrupts them; multi-writer DB
    #     replication is explicitly out of scope (roadmap §4.20). ---
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    # --- Host-path / machine-specific state (privacy: absolute paths) ---
    "*.log",
    "*.trace",
    "logs/",
    "telemetry/",
    "recovery/",
    ".slideshow_config.json",
    ".monitor_slideshow_daemon.json",
    ".phase_db_migration_state.json",
    ".extraction_history.json",
    # --- Large regenerable caches — not cross-device state ---
    "thumbnail-cache/",
    "storyboard-cache/",
    "listing-images/",
    # --- Lock / transient ---
    "*.lock",
    "*.pid",
)


class ConflictPolicy(Enum):
    NEWER_WINS = "newer_wins"
    PREFER_LOCAL = "prefer_local"
    PREFER_REMOTE = "prefer_remote"


@dataclass
class FileDiff:
    """Describes the sync action needed for one relative path."""

    relpath: str
    action: str  # "upload" | "download" | "conflict" | "skip"
    reason: str = ""
    local_mtime: float = 0.0
    remote_mtime: float = 0.0
    local_size: int = 0
    remote_size: int = 0


@dataclass
class SyncPlan:
    uploads: List[FileDiff] = field(default_factory=list)
    downloads: List[FileDiff] = field(default_factory=list)
    conflicts: List[FileDiff] = field(default_factory=list)
    skipped: List[FileDiff] = field(default_factory=list)


class LocalDirSyncEngine:
    """Pure-logic diff + conflict resolver.  No Qt, no network calls.

    Parameters
    ----------
    local_root:
        The local directory to sync (``~/.image-toolkit/``).
    remote_listing:
        Mapping of relative-path → ``{"mtime": float, "size": int}`` for
        every file currently on the remote.  Provided by the worker after
        fetching the remote listing via the cloud API.
    conflict_policy:
        How to resolve files that differ on both sides.
    excludes:
        Glob patterns for files/directories that must never be synced.
        Checked against the *relpath* component of each file.
    """

    def __init__(
        self,
        local_root: Path,
        remote_listing: Dict[str, Dict[str, Any]],
        conflict_policy: ConflictPolicy = ConflictPolicy.NEWER_WINS,
        excludes: Tuple[str, ...] = DEFAULT_EXCLUDES,
    ) -> None:
        self.local_root = local_root
        self.remote_listing = remote_listing
        self.conflict_policy = conflict_policy
        self.excludes = excludes

    def _is_excluded(self, relpath: str) -> bool:
        """Return True if *relpath* matches any exclude pattern."""
        import fnmatch

        name = Path(relpath).name
        parts = Path(relpath).parts
        for pat in self.excludes:
            # Match against the bare filename
            if fnmatch.fnmatch(name, pat.rstrip("/")):
                return True
            # Match against any path component (catches "secrets/", "logs/")
            for part in parts:
                if fnmatch.fnmatch(part, pat.rstrip("/")):
                    return True
            # Match against full relpath
            if fnmatch.fnmatch(relpath, pat):
                return True
        return False

    def _local_files(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for dirpath, _, filenames in os.walk(self.local_root):
            for fname in filenames:
                abs_path = Path(dirpath) / fname
                relpath = str(abs_path.relative_to(self.local_root))
                if self._is_excluded(relpath):
                    continue
                try:
                    st = abs_path.stat()
                    result[relpath] = {"mtime": st.st_mtime, "size": st.st_size}
                except OSError:
                    pass
        return result

    def _resolve_conflict(self, diff: FileDiff) -> str:
        """Return the winning action for a conflicted file."""
        if self.conflict_policy == ConflictPolicy.PREFER_LOCAL:
            return "upload"
        if self.conflict_policy == ConflictPolicy.PREFER_REMOTE:
            return "download"
        # NEWER_WINS — fall back to upload on tie
        if diff.local_mtime >= diff.remote_mtime:
            return "upload"
        return "download"

    def build_plan(self) -> SyncPlan:
        """Compute the full sync plan without touching any files."""
        plan = SyncPlan()
        local = self._local_files()
        remote = self.remote_listing

        all_paths = set(local) | set(remote)
        for relpath in sorted(all_paths):
            if self._is_excluded(relpath):
                plan.skipped.append(FileDiff(relpath=relpath, action="skip", reason="excluded"))
                continue

            in_local = relpath in local
            in_remote = relpath in remote

            if in_local and not in_remote:
                plan.uploads.append(
                    FileDiff(
                        relpath=relpath,
                        action="upload",
                        reason="local only",
                        local_mtime=local[relpath]["mtime"],
                        local_size=local[relpath]["size"],
                    )
                )
            elif in_remote and not in_local:
                plan.downloads.append(
                    FileDiff(
                        relpath=relpath,
                        action="download",
                        reason="remote only",
                        remote_mtime=remote[relpath]["mtime"],
                        remote_size=remote[relpath]["size"],
                    )
                )
            else:
                # Both sides — check for conflict
                lm = local[relpath]["mtime"]
                rm = remote[relpath]["mtime"]
                ls = local[relpath]["size"]
                rs = remote[relpath]["size"]
                # Same mtime+size → in sync
                if abs(lm - rm) < 2.0 and ls == rs:
                    plan.skipped.append(
                        FileDiff(relpath=relpath, action="skip", reason="in sync")
                    )
                    continue
                diff = FileDiff(
                    relpath=relpath,
                    action="conflict",
                    reason="both modified",
                    local_mtime=lm,
                    remote_mtime=rm,
                    local_size=ls,
                    remote_size=rs,
                )
                resolved = self._resolve_conflict(diff)
                diff.action = resolved
                diff.reason = f"conflict → {resolved} ({self.conflict_policy.value})"
                if resolved == "upload":
                    plan.uploads.append(diff)
                else:
                    plan.downloads.append(diff)

        return plan


# ---------------------------------------------------------------------------
# Worker signals
# ---------------------------------------------------------------------------

class LocalDirSyncSignals:  # not a QObject — use the worker's signals directly
    pass


# ---------------------------------------------------------------------------
# QThread worker
# ---------------------------------------------------------------------------

class LocalDirSyncWorker(QThread):
    """Bidirectional sync of ``~/.image-toolkit/`` ↔ remote ``.image-toolkit/``.

    Emits progress/status on the GUI thread via Qt signals.  The cyclic GC
    is disabled for the full ``run()`` (the #478 guard class — see
    ``gc_safe.py``).

    Parameters
    ----------
    auth_config:
        Same dict as the cloud sync workers receive from ``DriveSyncTab``.
    provider_text:
        Currently selected provider label.
    local_root:
        Local directory to sync (defaults to ``~/.image-toolkit/``).
    remote_folder:
        Remote folder name / path (defaults to ``.image-toolkit``).
    dry_run:
        If ``True``, compute and report the plan but make no changes.
    conflict_policy:
        Conflict resolution strategy.
    excludes:
        Extra glob patterns to exclude (merged with ``DEFAULT_EXCLUDES``).
    """

    status = Signal(str)        # log line
    progress = Signal(int, int) # (done, total)
    finished = Signal(bool, str, bool)  # (success, message, was_dry_run)

    def __init__(
        self,
        auth_config: Dict[str, Any],
        provider_text: str,
        local_root: Optional[Path] = None,
        remote_folder: str = ".image-toolkit",
        dry_run: bool = True,
        conflict_policy: ConflictPolicy = ConflictPolicy.NEWER_WINS,
        excludes: Tuple[str, ...] = (),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.auth_config = auth_config
        self.provider_text = provider_text
        self.local_root = local_root or (Path.home() / ".image-toolkit")
        self.remote_folder = remote_folder
        self.dry_run = dry_run
        self.conflict_policy = conflict_policy
        self.excludes: Tuple[str, ...] = DEFAULT_EXCLUDES + tuple(excludes)
        self._cancelled = False
        self._client = None  # cached provider client — one auth per run

    def stop(self) -> None:
        self._cancelled = True

    # alias
    cancel = stop

    def _log(self, msg: str) -> None:
        ts = time.strftime("[%H:%M:%S]")
        self.status.emit(f"{ts} {msg}")

    def run(self) -> None:  # noqa: C901
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            self._execute()
        except Exception as exc:  # never let a QThread die without notifying the GUI
            self.finished.emit(False, f"Local Directory Sync failed: {exc}", self.dry_run)
        finally:
            if was_enabled:
                gc.enable()
            self._client = None

    def _execute(self) -> None:  # noqa: C901
        self._log("=== Local Directory Sync ===")
        self._log(f"Local:  {self.local_root}")
        self._log(f"Remote: {self.remote_folder} ({self.provider_text})")
        self._log(f"Mode:   {'DRY RUN' if self.dry_run else 'LIVE'}")
        self._log(f"Conflict policy: {self.conflict_policy.value}")

        if not self.local_root.is_dir():
            self.finished.emit(
                False,
                f"Local directory does not exist: {self.local_root}",
                self.dry_run,
            )
            return

        try:
            remote_listing = self._fetch_remote_listing()
        except Exception as exc:
            self.finished.emit(False, f"Failed to fetch remote listing: {exc}", self.dry_run)
            return

        if self._cancelled:
            self.finished.emit(False, "Cancelled before sync.", self.dry_run)
            return

        engine = LocalDirSyncEngine(
            local_root=self.local_root,
            remote_listing=remote_listing,
            conflict_policy=self.conflict_policy,
            excludes=self.excludes,
        )
        plan = engine.build_plan()

        total = len(plan.uploads) + len(plan.downloads)
        self._log(
            f"Plan: {len(plan.uploads)} uploads, {len(plan.downloads)} downloads, "
            f"{len(plan.conflicts)} conflicts resolved, {len(plan.skipped)} skipped."
        )

        if self.dry_run:
            self._log_plan(plan)
            self.finished.emit(True, "Dry run complete — no files were changed.", self.dry_run)
            return

        done = 0
        self.progress.emit(done, total)

        # Uploads
        for diff in plan.uploads:
            if self._cancelled:
                self.finished.emit(False, "Sync cancelled.", self.dry_run)
                return
            try:
                self._upload(diff)
                self._log(f"↑ {diff.relpath}")
            except Exception as exc:
                self._log(f"ERROR uploading {diff.relpath}: {exc}")
            done += 1
            self.progress.emit(done, total)

        # Downloads
        for diff in plan.downloads:
            if self._cancelled:
                self.finished.emit(False, "Sync cancelled.", self.dry_run)
                return
            try:
                self._download(diff)
                self._log(f"↓ {diff.relpath}")
            except Exception as exc:
                self._log(f"ERROR downloading {diff.relpath}: {exc}")
            done += 1
            self.progress.emit(done, total)

        self.finished.emit(True, f"Sync complete — {total} files transferred.", self.dry_run)

    def _log_plan(self, plan: SyncPlan) -> None:
        if plan.uploads:
            self._log(f"  Would upload ({len(plan.uploads)}):")
            for d in plan.uploads:
                self._log(f"    ↑ {d.relpath}  [{d.reason}]")
        if plan.downloads:
            self._log(f"  Would download ({len(plan.downloads)}):")
            for d in plan.downloads:
                self._log(f"    ↓ {d.relpath}  [{d.reason}]")
        if plan.skipped:
            self._log(f"  Skipped: {len(plan.skipped)}")

    # ------------------------------------------------------------------
    # Provider dispatch — upload / download / remote listing
    # ------------------------------------------------------------------

    def _provider_client(self):
        """Return a cached cloud-client handle for the selected provider.

        Built once per ``run()`` — re-instantiating per file re-runs the OAuth
        / service-account handshake on every upload and download.
        """
        if self._client is not None:
            return self._client
        self._client = self._build_provider_client()
        return self._client

    def _build_provider_client(self):
        pt = self.provider_text
        if pt.startswith("Google Drive"):
            from backend.src.web.cloud.google_drive_sync import GoogleDriveSync
            return GoogleDriveSync(
                local_source_path=str(self.local_root),
                drive_destination_folder_name=self.remote_folder,
                dry_run=True,  # client used for listing/single ops
                logger=self._log,
                **self._google_kwargs(),
            )
        if pt == "Dropbox":
            from backend.src.web.cloud.dropbox_drive_sync import DropboxDriveSync
            return DropboxDriveSync(
                local_source_path=str(self.local_root),
                drive_destination_folder_name=self.remote_folder,
                access_token=self.auth_config.get("access_token", ""),
                dry_run=True,
                logger=self._log,
            )
        if pt == "OneDrive":
            from backend.src.web.cloud.one_drive_sync import OneDriveSync
            return OneDriveSync(
                local_source_path=str(self.local_root),
                drive_destination_folder_name=self.remote_folder,
                client_id=self.auth_config.get("client_id", ""),
                client_secret=self.auth_config.get("client_secret", ""),
                dry_run=True,
                logger=self._log,
            )
        raise ValueError(f"Unsupported provider: {self.provider_text}")

    def _google_kwargs(self) -> Dict[str, Any]:
        mode = self.auth_config.get("mode", "service_account")
        if mode == "service_account":
            return {
                "service_account_data": self.auth_config.get("service_account_data"),
                "client_secrets_data": None,
                "token_file": None,
            }
        return {
            "client_secrets_data": self.auth_config.get("client_secrets_data"),
            "token_file": self.auth_config.get("token_file"),
            "service_account_data": None,
        }

    def _fetch_remote_listing(self) -> Dict[str, Dict[str, Any]]:
        """Return relpath → {mtime, size} for all remote files."""
        client = self._provider_client()
        # Cloud sync backends expose list_remote_files() → list[dict]
        # with keys: "path" (relpath within remote_folder), "mtime", "size".
        raw: List[Dict[str, Any]] = []
        if hasattr(client, "list_remote_files"):
            raw = client.list_remote_files()
        return {
            item["path"]: {
                "mtime": float(item.get("mtime", 0)),
                "size": int(item.get("size", 0)),
            }
            for item in raw
        }

    def _upload(self, diff: FileDiff) -> None:
        local_path = self.local_root / diff.relpath
        client = self._provider_client()
        if hasattr(client, "upload_file"):
            client.upload_file(str(local_path), diff.relpath)

    def _download(self, diff: FileDiff) -> None:
        local_path = self.local_root / diff.relpath
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client = self._provider_client()
        if hasattr(client, "download_file"):
            client.download_file(diff.relpath, str(local_path))


__all__ = [
    "ConflictPolicy",
    "DEFAULT_EXCLUDES",
    "FileDiff",
    "LocalDirSyncEngine",
    "LocalDirSyncWorker",
    "SyncPlan",
]
