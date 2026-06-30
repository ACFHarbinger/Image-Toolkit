"""
backend/src/database/pooled_image_database.py
==============================================
psycopg3-backed connection pool for image database operations — §4.8.

``PooledPgvectorDatabase`` is a drop-in replacement for ``PgvectorImageDatabase``
that uses ``psycopg_pool.ConnectionPool`` instead of a single persistent
psycopg2 connection.  Every public method borrows a connection from the pool
for the duration of its own call, returns it automatically, and is therefore
fully thread-safe.  Multiple QThread workers (search, ingest, duplicate scan)
can execute database calls concurrently without racing on a shared connection.

Key differences from ``PgvectorImageDatabase``
-----------------------------------------------
* psycopg3 row factory ``psycopg.rows.dict_row`` replaces
  ``psycopg2.extras.DictCursor`` — rows are plain ``dict`` objects.
* ``execute_values`` bulk insert replaced by ``executemany()`` which psycopg3
  natively batches via server-side prepared statements.
* ``autocommit=True`` is the connection default.  Transactions use the context
  manager ``conn.transaction()`` instead of toggling ``autocommit``.
* VACUUM / REINDEX require ``autocommit=True`` on the connection — psycopg3
  exposes this as a connection parameter rather than a mutable attribute.
* ``_pool`` is a module-level singleton keyed by the DSN so multiple
  ``PooledPgvectorDatabase`` instances share one pool.

Pool configuration
------------------
``min_size`` (default 2) and ``max_size`` (default 10) control the pool bounds.
Override via ``PG_POOL_MIN`` / ``PG_POOL_MAX`` environment variables.

Usage
-----
::

    db = PooledPgvectorDatabase()          # same kwargs as PgvectorImageDatabase
    results = db.search_images(tags=["1girl"])
    db.close()                             # closes the pool (call once at shutdown)
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional

import psycopg
import psycopg_pool
from dotenv import load_dotenv
from psycopg.rows import dict_row

from .sql_loader import load_sql

_schema = load_sql("schema.sql")
_images = load_sql("images.sql")
_groups = load_sql("groups.sql")
_tags = load_sql("tags.sql")
_stats = load_sql("stats.sql")
_maintenance = load_sql("maintenance.sql")

# Module-level pool registry: DSN → ConnectionPool
_pools: Dict[str, psycopg_pool.ConnectionPool] = {}


def _get_pool(conninfo: str, min_size: int, max_size: int) -> psycopg_pool.ConnectionPool:
    if conninfo not in _pools:
        _pools[conninfo] = psycopg_pool.ConnectionPool(
            conninfo,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )
    return _pools[conninfo]


def _build_conninfo(params: Dict[str, Optional[str]]) -> str:
    mapping = {
        "dbname": "dbname",
        "user": "user",
        "password": "password",
        "host": "host",
        "port": "port",
    }
    parts = []
    for key, connkey in mapping.items():
        val = params.get(key)
        if val:
            # Escape spaces/special chars in value
            escaped = str(val).replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{connkey}={escaped}")
    return " ".join(parts)


class PooledPgvectorDatabase:
    """
    Thread-safe psycopg3 connection-pool-backed image database (§4.8).

    Drop-in replacement for ``PgvectorImageDatabase``.  All public methods
    have identical signatures and return types.

    Parameters
    ----------
    embed_dim : int
        Embedding vector dimension (default 128).
    db_name, db_user, db_password, db_host, db_port : str, optional
        Connection parameters.  Default to ``DB_*`` environment variables.
    env_path : str
        Path to a dotenv file loaded before env-var lookup.
    pool_min : int
        Minimum pool size (default: ``PG_POOL_MIN`` env var or 2).
    pool_max : int
        Maximum pool size (default: ``PG_POOL_MAX`` env var or 10).
    """

    def __init__(
        self,
        embed_dim: int = 128,
        db_name: Optional[str] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
        db_host: Optional[str] = None,
        db_port: Optional[str] = None,
        env_path: str = "env/vars.env",
        pool_min: int = 0,
        pool_max: int = 0,
    ) -> None:
        load_dotenv(dotenv_path=env_path)

        self.embedding_dim = embed_dim
        self._conn_params: Dict[str, Optional[str]] = {
            "dbname": db_name or os.getenv("DB_NAME"),
            "user": db_user or os.getenv("DB_USER"),
            "password": db_password or os.getenv("DB_PASSWORD"),
            "host": db_host or os.getenv("DB_HOST"),
            "port": db_port or os.getenv("DB_PORT"),
        }
        min_size = pool_min or int(os.getenv("PG_POOL_MIN", "2"))
        max_size = pool_max or int(os.getenv("PG_POOL_MAX", "10"))

        self._conninfo = _build_conninfo(self._conn_params)
        try:
            self._pool = _get_pool(self._conninfo, min_size, max_size)
        except Exception as exc:
            print(f"Error creating connection pool: {exc}", file=sys.stderr)
            raise

        self._create_tables()

    # ── Connection pool helpers ────────────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Generator[psycopg.Connection, None, None]:
        """Borrow a connection from the pool (context manager)."""
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def _transaction(self) -> Generator[psycopg.Connection, None, None]:
        """Borrow a connection in an explicit transaction block."""
        with self._pool.connection() as conn:
            with conn.transaction():
                yield conn

    # ── Schema initialisation ──────────────────────────────────────────────────

    def _create_tables(self) -> None:
        with self._conn() as conn:
            conn.execute(_schema["create_extension"])
            conn.execute(
                _schema["create_table_images"].format(
                    embedding_dim=self.embedding_dim
                )
            )
            conn.execute(_schema["create_table_groups"])
            conn.execute(_schema["create_table_subgroups"])
            conn.execute(_schema["create_table_tags"])
            conn.execute(_schema["create_table_image_tags"])
            conn.execute(_schema["create_index_group"])
            conn.execute(_schema["create_index_subgroup"])
            conn.execute(_schema["create_index_path"])
            conn.execute(_schema["create_index_embedding"])
            conn.execute(_schema["add_phash_column"])
            conn.execute(_schema["create_index_phash"])

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_or_create_group(self, conn: psycopg.Connection, name: str) -> int:
        row = conn.execute(_groups["upsert_group"], (name,)).fetchone()
        return row["id"]

    def _get_or_create_tag(self, conn: psycopg.Connection, name: str) -> int:
        row = conn.execute(_tags["upsert_tag_entity"], (name,)).fetchone()
        return row["id"]

    # ── Group / subgroup management ────────────────────────────────────────────

    def add_group(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("Group name cannot be empty")
        with self._conn() as conn:
            conn.execute(_groups["insert_group"], (name.strip(),))

    def add_subgroup(self, name: str, group_name: str) -> None:
        if not name or not name.strip() or not group_name or not group_name.strip():
            raise ValueError("Subgroup name and Group name cannot be empty")
        with self._conn() as conn:
            group_id = self._get_or_create_group(conn, group_name.strip())
            conn.execute(_groups["upsert_subgroup"], (name.strip(), group_id))

    def delete_group(self, name: str) -> None:
        with self._conn() as conn:
            conn.execute(_groups["delete_group"], (name,))

    def delete_subgroup(self, name: str, group_name: str) -> None:
        if not name or not group_name:
            raise ValueError("Subgroup name and Group name cannot be empty")
        with self._conn() as conn:
            conn.execute(_groups["delete_subgroup"], (name, group_name))

    def rename_group(self, old_name: str, new_name: str) -> None:
        if not old_name or not new_name or not new_name.strip():
            raise ValueError("Group names cannot be empty")
        if old_name == new_name:
            return
        with self._transaction() as conn:
            conn.execute(_groups["rename_group_in_images"], (new_name, old_name))
            conn.execute(_groups["rename_group_in_groups"], (new_name, old_name))

    def rename_subgroup(self, old_name: str, new_name: str, group_name: str) -> None:
        if not old_name or not new_name or not new_name.strip() or not group_name:
            raise ValueError("Subgroup and Group names cannot be empty")
        if old_name == new_name:
            return
        with self._transaction() as conn:
            conn.execute(
                _groups["rename_subgroup_in_images"],
                (new_name, old_name, group_name),
            )
            conn.execute(
                _groups["rename_subgroup_in_subgroups"],
                (new_name, old_name, group_name),
            )

    def get_all_groups(self, limit: int = 10000) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(_groups["get_all_groups"], (limit,)).fetchall()
        return [r["name"] for r in rows]

    def get_all_subgroups(self, limit: int = 10000) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(_groups["get_all_subgroups"], (limit,)).fetchall()
        return [r["name"] for r in rows]

    def get_subgroups_for_group(self, group_name: str, limit: int = 10000) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(
                _groups["get_subgroups_for_group"], (group_name, limit)
            ).fetchall()
        return [r["name"] for r in rows]

    def get_all_subgroups_detailed(self, limit: int = 10000) -> List[tuple]:
        # The SQL selects s.name, g.name — both columns named "name".
        # Use tuple_row to avoid dict_row silently discarding one of the duplicates.
        with self._conn() as conn:
            with conn.cursor(row_factory=psycopg.rows.tuple_row) as cur:
                cur.execute(_groups["get_all_subgroups_detailed"], (limit,))
                rows = cur.fetchall()
        return list(rows)

    # ── Tag management ─────────────────────────────────────────────────────────

    def add_tag(self, name: str, type: Optional[str] = None) -> None:
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty")
        type_value = type if type and type.strip() else None
        with self._conn() as conn:
            conn.execute(_tags["upsert_tag"], (name.strip(), type_value))

    def delete_tag(self, name: str) -> None:
        with self._conn() as conn:
            conn.execute(_tags["delete_tag"], (name,))

    def rename_tag(self, old_name: str, new_name: str) -> None:
        if not old_name or not new_name or not new_name.strip():
            raise ValueError("Tag names cannot be empty")
        if old_name == new_name:
            return
        with self._conn() as conn:
            conn.execute(_tags["rename_tag"], (new_name, old_name))

    def update_tag_type(self, name: str, new_type: str) -> None:
        type_value = new_type if new_type and new_type.strip() else None
        with self._conn() as conn:
            conn.execute(_tags["update_tag_type"], (type_value, name))

    def get_all_tags(self, limit: int = 10000) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(_tags["get_all_tags"], (limit,)).fetchall()
        return [r["name"] for r in rows]

    def get_all_tags_with_types(self, limit: int = 10000) -> List[Dict[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                _tags["get_all_tags_with_types"], (limit,)
            ).fetchall()
        return [{"name": r["name"], "type": r["type"] or ""} for r in rows]

    def get_image_tags(self, image_id: int) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(_tags["get_image_tags"], (image_id,)).fetchall()
        return [r["name"] for r in rows]

    # ── Image CRUD ─────────────────────────────────────────────────────────────

    def add_image(
        self,
        file_path: str,
        embedding: Optional[List[float]] = None,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> int:
        path = Path(file_path)
        now = datetime.now()

        if group_name and group_name.strip():
            self.add_group(group_name)
        if group_name and group_name.strip() and subgroup_name and subgroup_name.strip():
            self.add_subgroup(subgroup_name, group_name)

        with self._conn() as conn:
            row = conn.execute(
                _images["upsert_image"],
                (
                    str(path.absolute()),
                    path.name,
                    0,           # file_size
                    width,
                    height,
                    group_name,
                    subgroup_name,
                    now,
                    now,
                    embedding,
                    now,
                ),
            ).fetchone()
            image_id: int = row["id"]

            if tags is not None:
                conn.execute(_images["delete_image_tags"], (image_id,))
                if tags:
                    tag_ids = [self._get_or_create_tag(conn, t) for t in tags]
                    conn.executemany(
                        "INSERT INTO image_tags (image_id, tag_id) VALUES (%s, %s)"
                        " ON CONFLICT DO NOTHING",
                        [(image_id, tid) for tid in tag_ids],
                    )

        return image_id

    def delete_image(self, image_id: int) -> None:
        with self._conn() as conn:
            conn.execute(_images["delete_image"], (image_id,))

    def update_image(
        self,
        image_id: int,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        date_modified = datetime.now()
        with self._conn() as conn:
            set_clauses = ["date_modified = %s"]
            params: list = [date_modified]

            if group_name is not None:
                set_clauses.append("group_name = %s")
                params.append(group_name)
                if group_name and group_name.strip():
                    self.add_group(group_name)

            if subgroup_name is not None:
                set_clauses.append("subgroup_name = %s")
                params.append(subgroup_name)

            if len(set_clauses) > 1:
                sql = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %s"
                params.append(image_id)
                conn.execute(sql, tuple(params))

            if subgroup_name is not None:
                final_group_name = group_name
                if final_group_name is None:
                    row = conn.execute(
                        _images["get_image_group_name"], (image_id,)
                    ).fetchone()
                    if row:
                        final_group_name = row["group_name"]
                if (
                    subgroup_name.strip()
                    and final_group_name
                    and final_group_name.strip()
                ):
                    self.add_subgroup(subgroup_name, final_group_name)

            if tags is not None:
                conn.execute(_images["delete_image_tags"], (image_id,))
                for tag_name in tags:
                    tag_id = self._get_or_create_tag(conn, tag_name)
                    conn.execute(_images["insert_image_tag"], (image_id, tag_id))

    def _fetch_one_image_details(
        self, conn: psycopg.Connection, image_id: int
    ) -> Optional[Dict[str, Any]]:
        row = conn.execute(_images["get_image_by_id"], (image_id,)).fetchone()
        if not row:
            return None
        image_data = dict(row)
        image_data.pop("embedding", None)
        image_data["tags"] = [
            r["name"]
            for r in conn.execute(_tags["get_image_tags"], (image_id,)).fetchall()
        ]
        return image_data

    def get_image_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                _images["get_image_id_by_path"], (file_path,)
            ).fetchone()
            if not row:
                return None
            return self._fetch_one_image_details(conn, row["id"])

    # ── Search ─────────────────────────────────────────────────────────────────

    def search_images(
        self,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        filename_pattern: Optional[str] = None,
        input_formats: Optional[List[str]] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        base_select = "SELECT DISTINCT i.*"
        if query_vector:
            vector_str = str(query_vector).replace("[", "{").replace("]", "}")
            base_select += f", i.embedding <-> '{vector_str}' AS distance"

        query = base_select + " FROM images i"
        conditions: list = []
        params: list = []

        if tags:
            query += (
                " JOIN image_tags it ON i.id = it.image_id"
                " JOIN tags t ON it.tag_id = t.id"
            )
            tag_placeholders = ",".join(["%s"] * len(tags))
            conditions.append(f"t.name IN ({tag_placeholders})")
            params.extend(tags)

        if group_name:
            conditions.append("i.group_name ILIKE %s")
            params.append(f"%{group_name}%")

        if subgroup_name:
            conditions.append("i.subgroup_name ILIKE %s")
            params.append(f"%{subgroup_name}%")

        if filename_pattern:
            conditions.append("i.filename ILIKE %s")
            params.append(f"%{filename_pattern}%")

        if input_formats:
            ext_conditions = []
            for ext in input_formats:
                clean_ext = ext.strip().lstrip(".")
                ext_conditions.append("i.filename ILIKE %s")
                params.append(f"%.{clean_ext}")
            if ext_conditions:
                conditions.append(f"({' OR '.join(ext_conditions)})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if query_vector:
            query += " ORDER BY distance ASC NULLS LAST"
        else:
            query += " ORDER BY i.date_added DESC"

        query += f" LIMIT {limit}"

        results: List[Dict[str, Any]] = []
        with self._conn() as conn:
            if query_vector:
                conn.execute("SET LOCAL hnsw.ef_search = 80;")

            rows = conn.execute(query, params).fetchmany(limit)
            if not rows:
                return results

            image_ids = [r["id"] for r in rows]
            tag_rows = conn.execute(
                _tags["get_tags_for_images_bulk"], (image_ids,)
            ).fetchall()
            tags_by_id: Dict[int, List[str]] = {}
            for tr in tag_rows:
                tags_by_id.setdefault(tr["image_id"], []).append(tr["tag_name"])

            for row in rows:
                image_data = dict(row)
                image_data.pop("embedding", None)
                image_data["tags"] = tags_by_id.get(row["id"], [])
                results.append(image_data)

        return results

    # ── Statistics ─────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        # Use tuple_row so aggregate function column names don't matter.
        stats: Dict[str, Any] = {}
        with self._conn() as conn:
            with conn.cursor(row_factory=psycopg.rows.tuple_row) as cur:
                cur.execute(_stats["count_images"])
                stats["total_images"] = cur.fetchone()[0]
                cur.execute(_stats["count_tags"])
                stats["total_tags"] = cur.fetchone()[0]
                cur.execute(_stats["count_groups"])
                stats["total_groups"] = cur.fetchone()[0]
                cur.execute(_stats["count_subgroups"])
                stats["total_subgroups"] = cur.fetchone()[0]
                cur.execute(_stats["sum_file_size"])
                stats["total_file_size"] = cur.fetchone()[0] or 0
                cur.execute(_stats["max_date_added"])
                stats["last_sync_date"] = cur.fetchone()[0]
        return stats

    # ── Maintenance ────────────────────────────────────────────────────────────

    def maintenance_vacuum(self, full: bool = False) -> None:
        # VACUUM requires autocommit=True — open a fresh raw connection outside pool
        cmd = _maintenance["vacuum_full"] if full else _maintenance["vacuum"]
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            conn.execute(cmd)

    def maintenance_reindex(self) -> None:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            conn.execute(_maintenance["reindex"])

    def reset_database(self) -> None:
        with self._conn() as conn:
            conn.execute(_maintenance["drop_image_tags"])
            conn.execute(_maintenance["drop_images"])
            conn.execute(_maintenance["drop_tags"])
            conn.execute(_maintenance["drop_groups"])
            conn.execute(_maintenance["drop_subgroups"])
        self._create_tables()

    # ── §4.6 Perceptual-hash deduplication ─────────────────────────────────────

    def update_phash(self, image_id: int, phash_int: int) -> None:
        with self._conn() as conn:
            conn.execute(_images["update_phash"], (phash_int, image_id))

    def find_near_duplicates_by_phash(
        self,
        phash_int: int,
        threshold: int = 10,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                _images["find_near_duplicates_phash"],
                (phash_int, phash_int, threshold, limit),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "file_path": r["file_path"],
                "filename": r["filename"],
                "group_name": r["group_name"],
                "subgroup_name": r["subgroup_name"],
                "phash": r["phash"],
                "hamming_dist": r["hamming_dist"],
            }
            for r in rows
        ]

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the connection pool.  Call once at application shutdown."""
        if self._conninfo in _pools:
            _pools[self._conninfo].close()
            del _pools[self._conninfo]

    def __enter__(self) -> "PooledPgvectorDatabase":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
