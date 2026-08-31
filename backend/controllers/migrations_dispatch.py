"""Single CLI entry point for the ``backend/migrations/`` scripts.

Before this module, each migration was invoked directly
(``python -m backend.migrations.xxx``), with its own bespoke argument
parsing. This dispatcher gives them one consistent surface
(``migrations <subcommand>``), following the same
``dispatch_command(command, args)`` pattern as
:mod:`backend.controllers.backend_dispatch` — deferred imports, plain-dict
args, ``❌``-prefixed error printing rather than raising, so a failed
migration doesn't take down the whole CLI process with a traceback.
"""

from __future__ import annotations

import getpass
import sys


def _password(args: dict) -> str:
    return args.get("password") or getpass.getpass("Vault password: ")


def dispatch_backup(args: dict) -> None:
    try:
        from backend.backups import backup_all

        report = backup_all.run_backup()
        print(report)
    except Exception as e:
        print(f"❌ Backup failed: {e}", file=sys.stderr)


def dispatch_create_db(args: dict) -> None:
    try:
        from backend.migrations import create_library_db

        report = create_library_db.run(_password(args), args["account_name"], args.get("db_path"))
        print(report)
    except Exception as e:
        print(f"❌ create-db failed: {e}", file=sys.stderr)


def dispatch_migrate_listings(args: dict) -> None:
    try:
        from backend.migrations import migrate_listings

        report = migrate_listings.run(
            _password(args), args["account_name"],
            db_path=args.get("db_path"), legacy_db_path=args.get("legacy_db_path"),
        )
        print(report)
    except Exception as e:
        print(f"❌ migrate-listings failed: {e}", file=sys.stderr)


def dispatch_migrate_pgvector(args: dict) -> None:
    try:
        from backend.migrations import migrate_pgvector

        report = migrate_pgvector.run(
            _password(args), args["account_name"], db_path=args.get("db_path"),
        )
        print(report)
    except Exception as e:
        print(f"❌ migrate-pgvector failed: {e}", file=sys.stderr)


def dispatch_verify(args: dict) -> None:
    try:
        from backend.migrations import verify_migration

        report = verify_migration.run(
            _password(args), args["account_name"],
            db_path=args.get("db_path"), legacy_db_path=args.get("legacy_db_path"),
        )
        print(report)
    except Exception as e:
        print(f"❌ verify failed: {e}", file=sys.stderr)


def dispatch_run_all(args: dict) -> None:
    try:
        from backend.migrations import runner

        state = runner.run_all(
            _password(args), args["account_name"],
            db_path=args.get("db_path"), legacy_db_path=args.get("legacy_db_path"),
            skip_postgres=args.get("skip_postgres", False),
            force=args.get("force", False),
        )
        print(state)
    except Exception as e:
        print(f"❌ run-all failed: {e}", file=sys.stderr)


def dispatch_clean_benchmark_data(args: dict) -> None:
    try:
        from backend.migrations import clean_benchmark_data

        report = clean_benchmark_data.run(
            _password(args), args["account_name"],
            db_path=args.get("db_path"),
            dry_run=args.get("dry_run", False),
        )
        print(report)
    except Exception as e:
        print(f"❌ clean-benchmark-data failed: {e}", file=sys.stderr)


def dispatch_upgrade_tag_categories(args: dict) -> None:
    try:
        from backend.upgrades import upgrade_tag_categories

        report = upgrade_tag_categories.run(
            _password(args), args["account_name"], db_path=args.get("db_path"),
        )
        print(report)
    except Exception as e:
        print(f"❌ upgrade-tag-categories failed: {e}", file=sys.stderr)


_HANDLERS = {
    "backup": dispatch_backup,
    "create-db": dispatch_create_db,
    "migrate-listings": dispatch_migrate_listings,
    "migrate-pgvector": dispatch_migrate_pgvector,
    "verify": dispatch_verify,
    "run-all": dispatch_run_all,
    "clean-benchmark-data": dispatch_clean_benchmark_data,
    "upgrade-tag-categories": dispatch_upgrade_tag_categories,
}


def dispatch_command(args: dict) -> None:
    """Route ``args["migrations_command"]`` to its handler."""
    command = args.get("migrations_command")
    handler = _HANDLERS.get(command)
    if handler is None:
        print(f"Migrations command '{command}' is not recognised.", file=sys.stderr)
        return
    handler(args)
