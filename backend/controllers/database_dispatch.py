"""`database` command group: read-only search against an already-unlocked
session (DB.6 — the library moved from a standalone Postgres database to a
session-keyed unified store, so this CLI command can only run against an
already-open session, e.g. invoked from within the running app post
vault-unlock)."""

from __future__ import annotations

import sys


def dispatch_database(args: dict) -> None:
    command = args.get("db_command")
    if command == "search":
        query = args.get("query", "")
        limit = args.get("limit", 50)
        try:
            from backend.src.database.unified import session
            from backend.src.database.unified.facade import UnifiedImageDatabase

            db = UnifiedImageDatabase(session.get_session())
            results = db.search_images(filename_pattern=query, limit=limit)
            if not results:
                print("No results found.")
                return
            for img in results:
                print(
                    f"{img.get('id', '?'):>6} | {img.get('filename', '')} | "
                    f"{img.get('group_name', '')} / {img.get('subgroup_name', '')} | "
                    f"tags: {', '.join(img.get('tags', []))}"
                )
        except ImportError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Database search failed: {e}", file=sys.stderr)
    else:
        print(f"Database command '{command}' is not recognised.", file=sys.stderr)
        print("Available commands: search", file=sys.stderr)
