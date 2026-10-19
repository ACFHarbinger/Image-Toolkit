"""Backup / restore helpers for the library database.

Moved out of ``middleware.migrations`` so backup machinery lives on its own:

* :mod:`middleware.backups.backup_all` — the hard pre-migration backup gate
  (runner step ``000``); timestamped, SHA-256-checksummed copies of every
  store, with ``verify_manifest()`` for the gate re-check.
* :mod:`middleware.backups._backup_utils` — lightweight copy-the-DB-file +
  manifest + rollback helper shared by the one-off migration scripts.
"""
