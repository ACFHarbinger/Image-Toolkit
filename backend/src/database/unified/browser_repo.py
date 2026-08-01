"""Raw-table browsing for the Data Browser tab — DB.9.

Read-only access to the unified store's tables, schema, and row grids,
scoped down from the roadmap's full spec (schema/ER graphics view + gated
cell-edit mode) to the table-grid slice: table picker, paginated raw rows,
a WHERE-clause filter, and pagination -- the ER diagram and edit mode are
explicitly deferred (see moon/roadmaps/unified_database.md).

Every method that accepts a table name validates it against list_tables()
first -- an allowlist, never raw interpolation of user input into SQL.
The WHERE-clause filter accepted by query_table() is NOT parsed as SQL;
it is a basic keyword/character denylist (semicolons, DDL/DML verbs) to
keep the intentionally read-only browser from being used to mutate data,
not a guarantee against a determined, malicious WHERE clause. This is
acceptable here: this store is per-user, local, and already encrypted --
the browser's only purpose is protecting the read-only *contract* of this
tab from accidental misuse, not defending against a hostile actor with
the vault password.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_BANNED_WHERE_PATTERN = re.compile(
    r";|\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA|CREATE|REPLACE)\b",
    re.IGNORECASE,
)


class BrowserRepo:
    def __init__(self, db):
        self._db = db

    def list_tables(self) -> List[str]:
        """Real, user-facing table names -- excludes sqlite's own internal
        bookkeeping tables (sqlite_% -- sequence counters, etc.)."""
        rows = self._db.query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name",
            (),
        )
        return [r[0] for r in rows]

    def _check_table(self, table: str) -> None:
        if table not in self.list_tables():
            raise ValueError(f"Unknown table: {table!r}")

    def table_columns(self, table: str) -> List[Dict[str, Any]]:
        """[{"name": ..., "type": ..., "pk": bool}, ...] via PRAGMA
        table_info -- reusable for a future FK/ER view (DB.9, deferred)."""
        self._check_table(table)
        rows = self._db.query(f'PRAGMA table_info("{table}")', ())
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        return [
            {"name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])}
            for r in rows
        ]

    def table_row_count(self, table: str) -> int:
        self._check_table(table)
        return self._db.query(f'SELECT COUNT(*) FROM "{table}"', ())[0][0]

    def query_table(
        self,
        table: str,
        where_sql: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[str], List[tuple]]:
        """Returns (column_names, rows) for a read-only, paginated grid.

        Raises ValueError for an unknown table or a where_sql that looks
        like it's trying to mutate data (see this module's docstring for
        what that guard does and does not protect against).
        """
        self._check_table(table)
        columns = [c["name"] for c in self.table_columns(table)]

        sql = f'SELECT * FROM "{table}"'
        if where_sql and where_sql.strip():
            if _BANNED_WHERE_PATTERN.search(where_sql):
                raise ValueError(
                    "WHERE clause rejected: only read-only filter "
                    "expressions are allowed (no ';', no INSERT/UPDATE/"
                    "DELETE/DROP/ALTER/ATTACH/PRAGMA/CREATE/REPLACE)."
                )
            sql += f" WHERE {where_sql}"
        sql += " LIMIT ? OFFSET ?"

        rows = self._db.query(sql, (limit, offset))
        return columns, rows
