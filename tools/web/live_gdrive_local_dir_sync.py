#!/usr/bin/env python3
"""Live Local Directory Sync against the real Drive folder ``.image-toolkit``.

Local side is a throwaway tree under ``~/Downloads/Data/Tests/`` — never
``~/.image-toolkit``. Remote side is the ``.image-toolkit`` folder already
open in Drive (must be empty, or pass ``--force``).

Auth (first match wins):

  --token / $IT_GDRIVE_ACCESS_TOKEN
  --service-account / $IT_GDRIVE_SERVICE_ACCOUNT_JSON   (JSON key file)
  --token-file / $IT_GDRIVE_TOKEN_FILE                  (OAuth token.json)

Examples::

  source .venv/bin/activate
  python tools/web/live_gdrive_local_dir_sync.py --token-file ~/token.json
  IT_GDRIVE_ACCESS_TOKEN=ya29... python tools/web/live_gdrive_local_dir_sync.py
  python tools/web/live_gdrive_local_dir_sync.py --service-account ./sa.json --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]
_REMOTE_FOLDER = ".image-toolkit"
_SCRATCH_PARENT = Path.home() / "Downloads" / "Data" / "Tests"

_FORBIDDEN_SUFFIXES = (".vault", ".p12", ".pfx", ".pem", ".key")
_FORBIDDEN_NAMES = {
    "library.db",
    "library.db-wal",
    "library.db-shm",
    "listings_secure.db",
    ".slideshow_config.json",
}
_ALLOWED = {"theme.qss", "config/ui.json"}


def _scratch_tree(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "config" / "ui.json").write_text('{"theme":"dark","e2e":true}\n')
    (root / "theme.qss").write_text("QWidget { color: #ccc; }\n")
    (root / "keystore.vault").write_bytes(b"encrypted-vault")
    (root / "app.p12").write_bytes(b"pkcs12")
    (root / "library.db").write_bytes(b"sqlcipher")
    (root / "library.db-wal").write_bytes(b"wal")
    (root / "library.db-shm").write_bytes(b"shm")
    (root / "listings_secure.db").write_bytes(b"listings")
    (root / ".slideshow_config.json").write_text("{}\n")
    (root / "cryptography").mkdir()
    (root / "cryptography" / "my_secure_data-a.vault").write_bytes(b"key-material")
    (root / "secrets").mkdir()
    (root / "secrets" / "token.json").write_text("secret\n")
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_text("/home/pkhunter/leaked-path\n")
    (root / "telemetry").mkdir()
    (root / "telemetry" / "events.json").write_text("{}\n")
    (root / "thumbnail-cache").mkdir()
    (root / "thumbnail-cache" / "a.png").write_bytes(b"png")


def _forbidden(paths: list[str]) -> list[str]:
    bad = []
    for p in paths:
        name = Path(p).name
        parts = Path(p).parts
        if (
            name in _FORBIDDEN_NAMES
            or name.endswith(_FORBIDDEN_SUFFIXES)
            or any(
                part in ("cryptography", "secrets", "logs", "telemetry", "thumbnail-cache")
                for part in parts
            )
        ):
            bad.append(p)
    return bad


def _resolve_token(args: argparse.Namespace) -> str:
    token = (args.token or os.environ.get("IT_GDRIVE_ACCESS_TOKEN") or "").strip()
    if token:
        return token

    sa = args.service_account or os.environ.get("IT_GDRIVE_SERVICE_ACCOUNT_JSON")
    if sa:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        path = Path(sa).expanduser()
        creds = service_account.Credentials.from_service_account_file(
            str(path), scopes=_DRIVE_SCOPE
        )
        creds.refresh(Request())
        if not creds.token:
            raise SystemExit(f"service-account file produced no token: {path}")
        return creds.token

    token_file = args.token_file or os.environ.get("IT_GDRIVE_TOKEN_FILE")
    if token_file:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        path = Path(token_file).expanduser()
        creds = Credentials.from_authorized_user_file(str(path), _DRIVE_SCOPE)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds.valid or not creds.token:
            raise SystemExit(
                f"OAuth token file is not valid (refresh failed): {path}"
            )
        return creds.token

    raise SystemExit(
        "No Drive credentials. Pass one of:\n"
        "  --token / $IT_GDRIVE_ACCESS_TOKEN\n"
        "  --token-file / $IT_GDRIVE_TOKEN_FILE   (OAuth token.json from the app)\n"
        "  --service-account / $IT_GDRIVE_SERVICE_ACCOUNT_JSON"
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sync a fake local ~/.image-toolkit tree to Drive's .image-toolkit folder."
    )
    p.add_argument("--token", default="", help="Raw Drive v3 access token")
    p.add_argument("--token-file", default="", help="OAuth token.json (personal account)")
    p.add_argument("--service-account", default="", help="Service-account JSON key")
    p.add_argument(
        "--remote-folder",
        default=_REMOTE_FOLDER,
        help=f"Drive folder name under My Drive (default: {_REMOTE_FOLDER})",
    )
    p.add_argument("--dry-run-only", action="store_true", help="Stop after the dry-run plan")
    p.add_argument("--yes", action="store_true", help="Do not prompt before live upload")
    p.add_argument(
        "--force",
        action="store_true",
        help="Run live even if the remote folder is not empty",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    from backend.src.web.cloud.gdrive_file_client import GoogleDriveFileClient
    from gui.src.helpers.web.cloud.local_dir_sync_worker import LocalDirSyncWorker
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.instance() or QCoreApplication(sys.argv)

    token = _resolve_token(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    local_root = _SCRATCH_PARENT / f"itk-479-e2e-{stamp}"
    local_root.mkdir(parents=True)
    _scratch_tree(local_root)

    client = GoogleDriveFileClient(token, root_name=args.remote_folder)
    existing = [i["path"] for i in client.list_remote_files()]
    print(f"Local scratch: {local_root}")
    print(f"Remote folder: {args.remote_folder}/  ({len(existing)} file(s) already there)")
    if existing:
        for p in existing[:20]:
            print(f"  existing: {p}")
        if len(existing) > 20:
            print(f"  … {len(existing) - 20} more")
        if not args.force and not args.dry_run_only:
            print(
                "Remote is not empty. Re-run with --force if you still want to "
                "upload into it (denied files will still be skipped)."
            )
            return 2

    logs: list[str] = []
    worker = LocalDirSyncWorker(
        auth_config={},
        provider_text="Google Drive (Personal Account)",
        local_root=local_root,
        remote_folder=args.remote_folder,
        dry_run=True,
    )
    worker._client = client
    worker.status.connect(logs.append)
    worker._execute()
    for line in logs:
        print(line)

    if args.dry_run_only:
        print("Stopped after dry-run (--dry-run-only). Nothing was uploaded.")
        return 0

    if not args.yes:
        reply = input(
            f"LIVE upload allowed files into Drive '{args.remote_folder}'? [y/N] "
        ).strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted. Remote unchanged.")
            return 0

    logs.clear()
    worker.dry_run = False
    worker._execute()
    for line in logs:
        print(line)

    listing = [i["path"] for i in client.list_remote_files()]
    bad = _forbidden(listing)
    missing = sorted(_ALLOWED - set(listing))
    print("--- remote listing after live ---")
    for p in listing:
        print(f"  {p}")
    if missing or bad:
        print(f"FAIL  missing={missing}  forbidden_uploaded={bad}")
        return 1

    print("PASS  only the allowed files are on Drive.")
    print(
        f"Delete the contents of Drive folder '{args.remote_folder}' "
        f"({', '.join(sorted(_ALLOWED))}) when you are done."
    )
    print(f"Local scratch (safe to rm -rf): {local_root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        raise SystemExit(130) from None
