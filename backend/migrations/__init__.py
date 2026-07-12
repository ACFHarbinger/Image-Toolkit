"""Phase DB migration scripts — unified library database.

Order is mandatory and enforced by :mod:`backend.migrations.runner`:

    000_backup_all         hard backup gate (cannot be skipped)
    001_create_library_db  DDL + schema_version stamp
    002_migrate_listings   listings_secure.db -> library.db
    003_migrate_pgvector   PostgreSQL -> library.db (skippable if unreachable)
    004_verify_migration   row-count / integrity / checksum report

See moon/roadmaps/unified_database.md (DB.4).
"""
