"""Maintenance operations for the unified store — DB.3 / DB.6.

Backs the Library Maintenance panel (ex-DatabaseTab): statistics in the
legacy banner shape, vacuum/reindex/integrity, and a reset that is gated on
a fresh backup manifest (the roadmap's hard rule after the data-loss
incident).
"""

from __future__ import annotations

from typing import Any, Dict


class Maintenance:
    def __init__(self, db):
        self._db = db

    def statistics(self) -> Dict[str, Any]:
        """Legacy-banner-compatible statistics plus unified-store extras."""
        raw = self._db.statistics()
        tables = raw.get("tables", {})
        total_file_size = self._db.query(
            "SELECT COALESCE(SUM(file_size), 0) FROM images", ()
        )[0][0]
        last_modified = self._db.query(
            "SELECT MAX(date_modified) FROM images", ()
        )[0][0]
        return {
            # PgvectorImageDatabase.get_statistics() parity keys:
            "total_images": tables.get("images", 0),
            "total_tags": tables.get("tags", 0),
            "total_groups": tables.get("groups", 0),
            "total_subgroups": tables.get("subgroups", 0),
            "total_file_size": total_file_size,
            "last_sync_date": last_modified,
            # Unified-store extras:
            "total_media_items": tables.get("media_items", 0),
            "total_entities": tables.get("entities", 0),
            "total_embeddings": tables.get("embeddings", 0),
            "file_bytes": raw.get("file_bytes", 0),
            "schema_version": raw.get("schema_version", 0),
            "tables": tables,
        }

    def vacuum(self) -> None:
        self._db.vacuum()

    def reindex(self) -> None:
        self._db.reindex()

    def integrity_check(self) -> bool:
        return self._db.integrity_check()

    def reset_database(self, backup_manifest_path=None) -> None:
        """Delete ALL rows from every user table.

        Requires a verified backup manifest (see backend.migrations.backup_all)
        — refusing to run without one is deliberate.
        """
        from backend.migrations.backup_all import find_latest_manifest, verify_manifest

        manifest = backup_manifest_path or find_latest_manifest()
        if manifest is None:
            raise RuntimeError(
                "reset_database refused: no backup manifest found. Run the "
                "backup gate first (python -m backend.migrations.backup_all)."
            )
        problems = verify_manifest(manifest)
        if problems:
            raise RuntimeError(
                f"reset_database refused: backup does not verify: {problems}"
            )

        self._db.begin()
        try:
            for (name,) in self._db.query(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' "
                "AND name != 'schema_meta'",
                (),
            ):
                self._db.execute(f'DELETE FROM "{name}"', ())
        except Exception:
            self._db.rollback()
            raise
        self._db.commit()
        self._db.vacuum()
