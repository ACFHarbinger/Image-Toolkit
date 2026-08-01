"""GUI access to the unified library database session (Phase DB, DB.5).

``get_library_db(vault_manager, parent)`` is the single entry point the tabs
use. It opens the session on first call (Argon2id runs once) and, when the
library is empty while the legacy ``listings_secure.db`` still has data,
offers the roadmap's first-launch migration (backup gate included) behind a
modal progress dialog.

Returns ``None`` when the vault is locked or the store cannot be opened —
callers show their own "not saved / not loaded" messaging, same as the old
``_db_ctx()`` contract.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

logger = logging.getLogger(__name__)

# Session-scoped flags so a declined/failed migration doesn't re-prompt on
# every _load_data call.
_migration_offered = False
_open_failed = False


def _vault_credentials(vault_manager) -> Optional[tuple]:
    if (
        vault_manager
        and hasattr(vault_manager, "raw_password")
        and vault_manager.raw_password
    ):
        return vault_manager.raw_password, vault_manager.account_name
    return None


def get_library_db(vault_manager, parent=None):
    """Return the open session ``base.database.Database`` or ``None``."""
    global _open_failed

    creds = _vault_credentials(vault_manager)
    if creds is None:
        return None

    from backend.src.database.unified import session

    if session.is_open():
        db = session.get_session()
    else:
        if _open_failed:
            return None
        try:
            db = session.open_session(*creds)
        except Exception as e:  # noqa: BLE001 — engine raises RuntimeError
            _open_failed = True
            logger.exception("[library_session] failed to open library.db")
            QMessageBox.critical(
                parent,
                "Library Database Unavailable",
                "Could not open the unified library database:\n"
                f"{e}\n\nListings will not load or save until this is fixed.",
            )
            return None

    _maybe_offer_migration(db, vault_manager, parent)
    return session.get_session() if session.is_open() else None


def _maybe_offer_migration(db, vault_manager, parent) -> None:
    """First-launch migration prompt (roadmap DB.4): empty library + legacy
    data present → offer to run the full runner (backup gate first)."""
    global _migration_offered
    if _migration_offered:
        return
    _migration_offered = True

    from backend.migrations.migrate_listings import LEGACY_DB

    try:
        counts = db.query(
            "SELECT (SELECT count(*) FROM media_items) + "
            "(SELECT count(*) FROM entities)",
            (),
        )[0][0]
    except Exception:  # noqa: BLE001 — treat as non-empty; never block startup
        return
    if counts > 0 or not Path(LEGACY_DB).exists():
        return

    reply = QMessageBox.question(
        parent,
        "Library Upgrade Required",
        "Your listings live in the legacy encrypted store and the new "
        "unified library is empty.\n\n"
        "Migrate now? A full backup (listings DB, encrypted exports, and "
        "the PostgreSQL image index if reachable) will be created first, "
        "and the legacy stores are only read — never modified.\n\n"
        "You can also run it later from a terminal:\n"
        "    python -m backend.migrations.runner",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    run_migration_with_progress(vault_manager, parent)


def run_migration_with_progress(vault_manager, parent=None) -> bool:
    """Run the migration runner in a worker thread behind a modal progress
    dialog. Returns True on success. Reopens the session afterwards."""
    creds = _vault_credentials(vault_manager)
    if creds is None:
        return False
    password, salt = creds

    from backend.migrations import runner
    from backend.src.database.unified import session

    # The runner opens its own handles on library.db — release ours first.
    session.close_session()

    progress = QProgressDialog(
        "Preparing migration…", "", 0, 0, parent
    )
    progress.setWindowTitle("Migrating to the Unified Library")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.show()

    result = {"error": None}

    def log(line: str) -> None:
        logger.info("[migration] %s", line)

    def work() -> None:
        try:
            runner.run_all(password, salt, log=log)
        except Exception as e:  # noqa: BLE001 — surfaced in the dialog below
            result["error"] = e

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    while thread.is_alive():
        QApplication.processEvents()
        thread.join(0.05)
    progress.close()

    # Reopen the session regardless of outcome so the tabs keep working.
    try:
        session.open_session(password, salt)
    except Exception:  # noqa: BLE001
        logger.exception("[library_session] reopen after migration failed")

    if result["error"] is not None:
        QMessageBox.critical(
            parent,
            "Migration Failed",
            f"The migration did not complete:\n{result['error']}\n\n"
            "Your data is untouched — the legacy stores are read-only during "
            "migration and a verified backup exists under "
            "assets/migrations/pre_unified/. Fix the issue and re-run:\n"
            "    python -m backend.migrations.runner",
        )
        return False

    QMessageBox.information(
        parent,
        "Migration Complete",
        "Listings (and the image index, if PostgreSQL was reachable) were "
        "migrated into the unified library and verified.",
    )
    return True
