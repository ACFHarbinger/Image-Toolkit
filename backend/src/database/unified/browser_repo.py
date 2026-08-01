"""Raw-table browsing for the Data Browser tab — DB.9.

Read-only access to the unified store's tables, schema, and row grids --
table picker, paginated raw rows, a WHERE-clause filter, pagination,
FK-navigation/reverse-references, and the schema/ER view are all
implemented on the GUI side (gui/src/tabs/database/data_browser_tab/).

``update_cell()`` is the one write path (DB.9's gated, session-only edit
mode) -- deliberately narrow: single-cell, single-column, scalar writes
with real validation, not a general SQL editor. It refuses primary-key
and foreign-key column edits outright (see its docstring).

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

    def table_foreign_keys(self, table: str) -> List[Dict[str, Any]]:
        """[{"column": ..., "ref_table": ..., "ref_column": ...}, ...] via
        PRAGMA foreign_key_list -- drives the Data Browser's FK-cell
        navigation and reverse_references() below."""
        self._check_table(table)
        rows = self._db.query(f'PRAGMA foreign_key_list("{table}")', ())
        # PRAGMA foreign_key_list columns: id, seq, table, from, to, on_update, on_delete, match
        return [
            {"column": r[3], "ref_table": r[2], "ref_column": r[4]}
            for r in rows
        ]

    def reverse_references(self, table: str, pk_value: Any) -> List[Dict[str, Any]]:
        """For a specific row (identified by its PK value) in *table*, find
        every OTHER table with a FK column pointing at *table*, and count
        how many of its rows reference this specific value -- e.g.
        [{"table": "images", "column": "group_id", "count": 214}, ...].

        Scans every table's FK list (cheap: list_tables() is small in this
        per-user store) rather than requiring the caller to know the
        reverse-reference graph up front.
        """
        self._check_table(table)
        results: List[Dict[str, Any]] = []
        for other_table in self.list_tables():
            for fk in self.table_foreign_keys(other_table):
                if fk["ref_table"] != table:
                    continue
                count = self._db.query(
                    f'SELECT COUNT(*) FROM "{other_table}" WHERE "{fk["column"]}" = ?',
                    (pk_value,),
                )[0][0]
                if count:
                    results.append({
                        "table": other_table,
                        "column": fk["column"],
                        "count": count,
                    })
        return results

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

    def update_cell(
        self, table: str, pk_column: str, pk_value: Any, column: str, new_value: Any
    ) -> None:
        """Write a single scalar cell -- DB.9's gated edit mode.

        Validates *table* against list_tables() and both *column* and
        *pk_column* against that table's real columns (table_columns())
        before building a fully parameterized UPDATE (only the
        already-validated identifiers are interpolated; *new_value* and
        *pk_value* are always bound parameters, never interpolated).

        Refuses to edit:
        - a primary-key column (repointing a PK is a different, riskier
          operation than a scalar cell edit -- not supported here);
        - a foreign-key column (writing a raw FK integer without
          validating it references an existing row could silently create
          a dangling reference -- not supported here; use the grid's
          FK-cell click-to-navigate instead of hand-editing the id).
        """
        self._check_table(table)
        columns_by_name = {c["name"]: c for c in self.table_columns(table)}

        if column not in columns_by_name:
            raise ValueError(f"Unknown column: {column!r} in table {table!r}")
        if pk_column not in columns_by_name:
            raise ValueError(
                f"Unknown primary-key column: {pk_column!r} in table {table!r}"
            )
        if columns_by_name[column]["pk"]:
            raise ValueError(
                f"Editing primary-key column {column!r} is not supported."
            )
        fk_columns = {fk["column"] for fk in self.table_foreign_keys(table)}
        if column in fk_columns:
            raise ValueError(
                f"Editing foreign-key column {column!r} is not supported -- "
                "use the grid's FK-cell click-to-navigate instead of "
                "hand-editing the raw id."
            )

        self._db.execute(
            f'UPDATE "{table}" SET "{column}" = ? WHERE "{pk_column}" = ?',
            (new_value, pk_value),
        )
