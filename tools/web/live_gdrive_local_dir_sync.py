#!/usr/bin/env python3
"""Live Local Directory Sync against the real Drive folder ``.image-toolkit``.

Local side is a throwaway tree under ``~/Downloads/Data/Tests/`` — never
``~/.image-toolkit``. Remote side is the ``.image-toolkit`` folder already
open in Drive (must be empty, or pass ``--force``).

Auth: opens a browser Google login by default (same InstalledAppFlow as
the desktop app). Cached at ``~/Downloads/Data/Tests/gdrive-e2e-token.json``
so the next run skips the browser if the refresh token is still valid.

  source .venv/bin/activate
  python tools/web/live_gdrive_local_dir_sync.py
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(str(_REPO))

_DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]
_REMOTE_FOLDER = ".image-toolkit"
_SCRATCH_PARENT = Path.home() / "Downloads" / "Data" / "Tests"
_E2E_TOKEN_FILE = _SCRATCH_PARENT / "gdrive-e2e-token.json"
_CLIENT_SECRET_PLAIN = _REPO / "assets" / "api" / "client_secret.json"
_CLIENT_SECRET_ENC = _REPO / "assets" / "api" / "client_secret.json.enc"

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


def _default_account() -> str:
    secrets = Path.home() / ".image-toolkit" / "secrets"
    stores = sorted(secrets.glob("my_keystore-*.p12"))
    if not stores:
        return "a"
    stem = stores[0].stem  # my_keystore-a
    _, _, suffix = stem.partition("-")
    return suffix or "a"


def _as_client_config(data: dict) -> dict:
    if "installed" in data or "web" in data:
        return data
    return {"installed": data}


def _load_json_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"not a JSON object: {path}")
    return data


def _decrypt_client_secret(account: str, password: str) -> dict:
    import backend.src.constants.crypto as udef
    from backend.src.constants.paths import API_DIR
    from backend.src.core.vault_manager import SecureJsonVault, VaultManager

    udef.update_cryptographic_values(account)
    vm = VaultManager()
    vm.load_keystore(udef.KEYSTORE_FILE, password)
    vm.get_secret_key(udef.KEY_ALIAS, password)
    if not vm.secret_key:
        raise SystemExit("could not derive the vault secret key (wrong password?)")
    enc = Path(API_DIR) / "client_secret.json.enc"
    if not enc.is_file():
        enc = _CLIENT_SECRET_ENC
    if not enc.is_file():
        raise SystemExit(f"no encrypted OAuth client_secret at {enc}")
    raw = SecureJsonVault(vm.secret_key, str(enc)).loadData()
    data = json.loads(str(raw))
    if not isinstance(data, dict):
        raise SystemExit(f"decrypted client_secret is not a JSON object: {enc}")
    return data


def _load_client_secrets(args: argparse.Namespace) -> dict:
    path = args.client_secrets or os.environ.get("IT_GDRIVE_CLIENT_SECRETS")
    if path:
        return _load_json_file(Path(path).expanduser())
    if _CLIENT_SECRET_PLAIN.is_file():
        return _load_json_file(_CLIENT_SECRET_PLAIN)
    if _CLIENT_SECRET_ENC.is_file():
        account = args.account or _default_account()
        password = getpass.getpass(
            f"Vault password for account '{account}' "
            "(decrypts assets/api/client_secret.json.enc): "
        )
        if not password:
            raise SystemExit("vault password required to start the browser OAuth flow")
        return _decrypt_client_secret(account, password)
    raise SystemExit(
        "Need a Google OAuth desktop client JSON to open the browser.\n"
        "Pass --client-secrets /path/to/client_secret.json "
        "(the same file Cloud Sync imports as 'client_secret')."
    )


def _save_creds(creds, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())


def _token_from_file(path: Path) -> str | None:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not path.is_file():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(path), _DRIVE_SCOPE)
    except Exception:
        return None
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_creds(creds, path)
        except Exception:
            return None
    if creds.valid and creds.token:
        return creds.token
    return None


def _browser_oauth(client_config: dict, save_to: Path) -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        _as_client_config(client_config), scopes=_DRIVE_SCOPE
    )
    print("Opening a browser window for Google Drive authorization…", flush=True)
    creds = flow.run_local_server(
        port=0,
        open_browser=True,
        authorization_prompt_message="If the browser does not open, visit:\n{url}\n",
        success_message="Drive access granted. You can close this tab and return to the terminal.",
    )
    if not creds or not creds.token:
        raise SystemExit("browser OAuth did not produce an access token")
    _save_creds(creds, save_to)
    print(f"Saved refresh token to {save_to} (next run will skip the browser).")
    return creds.token


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

    save_to = Path(
        args.token_file or os.environ.get("IT_GDRIVE_TOKEN_FILE") or _E2E_TOKEN_FILE
    ).expanduser()
    cached = _token_from_file(save_to)
    if cached:
        print(f"Using cached OAuth token from {save_to}")
        return cached

    return _browser_oauth(_load_client_secrets(args), save_to)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sync a fake local ~/.image-toolkit tree to Drive's .image-toolkit folder."
    )
    p.add_argument(
        "--token",
        default="",
        help="Raw Drive v3 access token (skips the browser)",
    )
    p.add_argument(
        "--token-file",
        default="",
        help="OAuth token.json to reuse/write (default: ~/Downloads/Data/Tests/gdrive-e2e-token.json)",
    )
    p.add_argument(
        "--client-secrets",
        default="",
        help="OAuth desktop client_secret.json (otherwise decrypted from the vault)",
    )
    p.add_argument(
        "--account",
        default="",
        help="Vault account name used to decrypt client_secret.json.enc (default: auto)",
    )
    p.add_argument("--service-account", default="", help="Service-account JSON key (skips the browser)")
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


def _load_sync_worker():
    """Load LocalDirSyncWorker without importing gui.src.helpers.__init__
    (that package pulls MainWindow → asp_backend)."""
    import importlib.util

    path = _REPO / "gui" / "src" / "helpers" / "web" / "cloud" / "local_dir_sync_worker.py"
    spec = importlib.util.spec_from_file_location("itk_local_dir_sync_worker", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.LocalDirSyncWorker


def main() -> int:
    print("Image-Toolkit live Drive Local Directory Sync", flush=True)
    args = _parse_args()
    from backend.src.web.cloud.gdrive_file_client import GoogleDriveFileClient
    from PySide6.QtCore import QCoreApplication

    LocalDirSyncWorker = _load_sync_worker()

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
