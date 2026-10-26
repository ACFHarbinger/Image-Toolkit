"""Attach library stores from an already-open session.

Nothing in this module opens ``~/.image-toolkit/library.db`` or calls
``session.open_session``. A missing session leaves the sidecar stores
unset so handlers keep returning ``available: false``. A session handle is wrapped with ``UnifiedImageDatabase`` when
``backend.database`` imports. If that engine cannot be imported, the
library stays unavailable. ``MemoryLibraryStore`` is only for an
explicitly injected test double.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from middleware.src.services.scan.service import ScanService

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLES = ("groups", "images", "subgroups", "tags")


def attach_library(server: Any, session: Any | None) -> None:
    """Set ``library_store``, ``library_admin_store``, and ``scan_service``.

    ``session`` is either ``None``, an object that already implements the
    handler methods, or an open database handle. This function never
    creates a database file.
    """
    if session is None:
        _clear_stores(server)
        return
    try:
        store = coerce_store(session)
    except PersistentStoreUnavailable:
        _clear_stores(server)
        return
    server.library_store = store
    server.library_admin_store = store
    server.scan_service = ScanService(db_session=store)


def _clear_stores(server: Any) -> None:
    server.library_store = None
    server.library_admin_store = None
    server.scan_service = None


class PersistentStoreUnavailable(RuntimeError):
    """The encrypted library engine cannot be constructed for this handle."""


def coerce_store(session: Any) -> Any:
    """Return the store the handlers should call."""
    if _is_ready_store(session):
        return session
    if _is_facade(session):
        return SqlLibraryStore(session, session._db)
    if not _database_importable():
        raise PersistentStoreUnavailable("backend.database is not available")
    from middleware.src.database.unified.facade import UnifiedImageDatabase

    try:
        facade = UnifiedImageDatabase(session)
    except ImportError as exc:
        raise PersistentStoreUnavailable("backend.database is not available") from exc
    return SqlLibraryStore(facade, session)


def _database_importable() -> bool:
    try:
        import backend.database  # noqa: F401
    except ImportError:
        return False
    return True


def _is_ready_store(session: Any) -> bool:
    return (
        callable(getattr(session, "search_files", None))
        and callable(getattr(session, "browse_page", None))
        and callable(getattr(session, "add_group", None))
    )


def _is_facade(session: Any) -> bool:
    return callable(getattr(session, "search_files", None)) and hasattr(session, "_db")


class SqlLibraryStore:
    """Facade plus equality-only browsing. No free-form SQL."""

    def __init__(self, facade: Any, raw: Any) -> None:
        self._facade = facade
        self._raw = raw

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    def list_tables(self) -> list[str]:
        from middleware.src.database.unified.browser_repo import BrowserRepo

        return list(BrowserRepo(self._raw).list_tables())

    def browse_page(
        self,
        table: str,
        column: str | None,
        equals: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[str], list[tuple[Any, ...]], int]:
        from middleware.src.database.unified.browser_repo import BrowserRepo

        browser = BrowserRepo(self._raw)
        if table not in browser.list_tables():
            raise ValueError(f"Unknown table: {table}")
        names = [str(item["name"]) for item in browser.table_columns(table)]
        table_sql = _quote_ident(table, names_ok=browser.list_tables())
        if column:
            column_sql = _quote_ident(column, names_ok=names)
            rows = self._raw.query(
                f'SELECT * FROM "{table_sql}" WHERE CAST("{column_sql}" AS TEXT) = ? LIMIT ? OFFSET ?',
                (equals, int(limit), int(offset)),
            )
            count = self._raw.query(
                f'SELECT COUNT(*) FROM "{table_sql}" WHERE CAST("{column_sql}" AS TEXT) = ?',
                (equals,),
            )[0][0]
        else:
            rows = self._raw.query(
                f'SELECT * FROM "{table_sql}" LIMIT ? OFFSET ?',
                (int(limit), int(offset)),
            )
            count = browser.table_row_count(table)
        return names, [tuple(row) for row in rows], int(count)

    def delete_image_by_path(self, path: str) -> bool:
        row = self._facade.get_image_by_path(path)
        if not row:
            return False
        self._facade.delete_image(row["id"])
        return True

    def paths_in_db(self, paths: list[str]) -> set[str]:
        return set(self._facade.paths_in_db(list(paths)))


class MemoryLibraryStore:
    """In-memory handler surface for tests that inject this object."""

    def __init__(self) -> None:
        self.groups: dict[str, set[str]] = {}
        self.tags: dict[str, str] = {}
        self.images: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def add_group(self, name: str) -> None:
        self.groups.setdefault(name, set())

    def add_subgroup(self, name: str, group_name: str) -> None:
        self.groups.setdefault(group_name, set()).add(name)

    def add_tag(self, name: str, category: str | None = None) -> None:
        self.tags.setdefault(name, category or "")

    def delete_group(self, name: str) -> None:
        self.groups.pop(name, None)
        for image in self.images.values():
            if image.get("group_name") == name:
                image["group_name"] = None
                image["subgroup_name"] = None

    def delete_subgroup(self, name: str, group_name: str) -> None:
        self.groups.get(group_name, set()).discard(name)
        for image in self.images.values():
            if image.get("group_name") == group_name and image.get("subgroup_name") == name:
                image["subgroup_name"] = None

    def delete_tag(self, name: str) -> None:
        self.tags.pop(name, None)
        for image in self.images.values():
            image["tags"] = [tag for tag in image["tags"] if tag != name]

    def merge_tags(self, source_name: str, dest_name: str) -> None:
        if source_name not in self.tags and dest_name not in self.tags:
            raise KeyError(f"tag not found: {source_name}")
        category = self.tags.get(dest_name, self.tags.get(source_name, ""))
        self.tags[dest_name] = category
        self.tags.pop(source_name, None)
        for image in self.images.values():
            image["tags"] = [dest_name if tag == source_name else tag for tag in image["tags"]]

    def rename_group(self, old_name: str, new_name: str) -> None:
        if old_name not in self.groups:
            raise KeyError(f"group not found: {old_name}")
        if not new_name.strip():
            raise ValueError("Group name cannot be empty")
        self.groups[new_name] = self.groups.pop(old_name)
        for image in self.images.values():
            if image.get("group_name") == old_name:
                image["group_name"] = new_name

    def rename_subgroup(self, old_name: str, new_name: str, group_name: str) -> None:
        members = self.groups.get(group_name)
        if members is None or old_name not in members:
            raise KeyError(f"subgroup not found: {old_name} in {group_name}")
        if not new_name.strip():
            raise ValueError("Subgroup name cannot be empty")
        members.remove(old_name)
        members.add(new_name)
        for image in self.images.values():
            if image.get("group_name") == group_name and image.get("subgroup_name") == old_name:
                image["subgroup_name"] = new_name

    def rename_tag(self, old_name: str, new_name: str) -> None:
        if old_name not in self.tags:
            raise KeyError(f"tag not found: {old_name}")
        self.tags[new_name] = self.tags.pop(old_name)
        for image in self.images.values():
            image["tags"] = [new_name if tag == old_name else tag for tag in image["tags"]]

    def update_tag_category(self, name: str, new_category: str | None) -> None:
        if name not in self.tags:
            raise KeyError(f"tag not found: {name}")
        self.tags[name] = new_category or ""

    def add_image(
        self,
        file_path: str,
        embedding: Any = None,
        group_name: str | None = None,
        subgroup_name: str | None = None,
        tags: list[str] | None = None,
        width: int | None = None,
        height: int | None = None,
        **_kwargs: Any,
    ) -> int:
        del embedding
        key = str(Path(file_path).absolute())
        current = self.images.get(key)
        image_id = int(current["id"]) if current else self._next_id
        if current is None:
            self._next_id += 1
        if group_name and group_name.strip():
            self.add_group(group_name)
        if subgroup_name and subgroup_name.strip() and group_name and group_name.strip():
            self.add_subgroup(subgroup_name, group_name)
        record = current or {
            "id": image_id,
            "file_path": key,
            "filename": Path(key).name,
            "tags": [],
            "group_name": None,
            "subgroup_name": None,
            "width": None,
            "height": None,
        }
        if group_name is not None:
            record["group_name"] = group_name.strip() or None
        if subgroup_name is not None:
            record["subgroup_name"] = subgroup_name.strip() or None
        if width is not None:
            record["width"] = width
        if height is not None:
            record["height"] = height
        if tags is not None:
            clean = [tag.strip() for tag in tags if tag and tag.strip()]
            record["tags"] = clean
            for tag in clean:
                self.add_tag(tag, None)
        record["id"] = image_id
        record["file_path"] = key
        record["filename"] = Path(key).name
        self.images[key] = record
        return image_id

    def get_image_by_path(self, file_path: str) -> dict[str, Any] | None:
        key = str(Path(file_path).absolute())
        current = self.images.get(key)
        if current is None:
            current = self.images.get(file_path)
        if current is None:
            return None
        item = dict(current)
        item["tags"] = list(current.get("tags") or [])
        return item

    def update_image(
        self,
        image_id: int,
        group_name: str | None = None,
        subgroup_name: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """None leaves a field. ``""`` clears it. Clearing the group clears the subgroup."""
        record = next((image for image in self.images.values() if int(image["id"]) == int(image_id)), None)
        if record is None:
            raise KeyError(f"image not found: {image_id}")
        group_cleared = False
        if group_name is not None:
            cleaned = group_name.strip()
            if cleaned:
                self.add_group(cleaned)
                record["group_name"] = cleaned
            else:
                record["group_name"] = None
                record["subgroup_name"] = None
                group_cleared = True
        if not group_cleared and subgroup_name is not None:
            cleaned_sub = subgroup_name.strip()
            if cleaned_sub:
                parent = record.get("group_name")
                if not parent:
                    raise ValueError("cannot set a subgroup on an image without a group")
                self.add_subgroup(cleaned_sub, str(parent))
                record["subgroup_name"] = cleaned_sub
            else:
                record["subgroup_name"] = None
        if tags is not None:
            clean = [tag.strip() for tag in tags if tag and tag.strip()]
            record["tags"] = clean
            for tag in clean:
                self.add_tag(tag, None)

    def delete_image_by_path(self, path: str) -> bool:
        key = str(Path(path).absolute())
        if key not in self.images and path not in self.images:
            return False
        self.images.pop(key, None)
        self.images.pop(path, None)
        return True

    def paths_in_db(self, paths: list[str]) -> set[str]:
        known = set(self.images)
        return {path for path in paths if path in known or str(Path(path).absolute()) in known}

    def search_files(self, **query_params: Any) -> list[dict[str, Any]]:
        rows = [dict(image) for image in self.images.values()]
        rows.sort(key=lambda image: int(image["id"]))
        groups = [str(name) for name in (query_params.get("group_names") or [])]
        if not groups and query_params.get("group_name"):
            groups = [str(query_params["group_name"])]
        subgroups = [str(name) for name in (query_params.get("subgroup_names") or [])]
        if not subgroups and query_params.get("subgroup_name"):
            subgroups = [str(query_params["subgroup_name"])]
        tags = [str(tag) for tag in (query_params.get("tags") or [])]
        pattern = str(query_params.get("filename_pattern") or "").casefold()
        formats = [str(fmt).lstrip(".").casefold() for fmt in (query_params.get("input_formats") or [])]
        if groups:
            wanted = {name.casefold() for name in groups}
            rows = [row for row in rows if str(row.get("group_name") or "").casefold() in wanted]
        if subgroups:
            wanted = {name.casefold() for name in subgroups}
            rows = [row for row in rows if str(row.get("subgroup_name") or "").casefold() in wanted]
        if tags:
            wanted = {tag.casefold() for tag in tags}
            rows = [row for row in rows if wanted.intersection({str(tag).casefold() for tag in row.get("tags") or []})]
        if pattern:
            rows = [row for row in rows if pattern in str(row.get("filename") or "").casefold()]
        if formats:
            rows = [
                row
                for row in rows
                if any(str(row.get("filename") or "").casefold().endswith("." + fmt) for fmt in formats)
            ]
        limit = query_params.get("limit", 10_000)
        try:
            limit_n = int(limit)
        except (TypeError, ValueError):
            limit_n = 10_000
        copied = []
        for row in rows[:limit_n]:
            item = dict(row)
            item["tags"] = list(row.get("tags") or [])
            copied.append(item)
        return copied

    def get_all_tags(self, limit: int = 10_000) -> list[str]:
        return sorted(self.tags)[:limit]

    def get_all_groups(self, limit: int = 10_000) -> list[str]:
        return sorted(self.groups)[:limit]

    def get_all_subgroups_detailed(self, limit: int = 10_000) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for group, members in self.groups.items():
            for subgroup in members:
                pairs.append((subgroup, group))
        return pairs[:limit]

    def get_all_tags_with_categories(self) -> list[dict[str, str]]:
        return [{"name": name, "category": category} for name, category in sorted(self.tags.items())]

    def list_tables(self) -> list[str]:
        return list(_TABLES)

    def browse_page(
        self,
        table: str,
        column: str | None,
        equals: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[str], list[tuple[Any, ...]], int]:
        columns, rows = _memory_table(self, table)
        if column:
            if column not in columns:
                raise ValueError(f"Unknown column: {column}")
            index = columns.index(column)
            rows = [row for row in rows if row[index] == equals]
        page = rows[int(offset) : int(offset) + int(limit)]
        return columns, page, len(rows)


def _memory_table(store: MemoryLibraryStore, table: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    if table == "groups":
        return ["name"], [(name,) for name in sorted(store.groups)]
    if table == "subgroups":
        rows = []
        for group, members in sorted(store.groups.items()):
            for subgroup in sorted(members):
                rows.append((subgroup, group))
        return ["name", "group_name"], rows
    if table == "tags":
        return ["name", "category"], [(name, category) for name, category in sorted(store.tags.items())]
    if table == "images":
        columns = ["id", "file_path", "filename", "group_name", "subgroup_name", "tags"]
        rows = []
        for image in store.search_files():
            rows.append(
                (
                    str(image["id"]),
                    str(image["file_path"]),
                    str(image["filename"]),
                    str(image.get("group_name") or ""),
                    str(image.get("subgroup_name") or ""),
                    ",".join(image.get("tags") or []),
                )
            )
        return columns, rows
    raise ValueError(f"Unknown table: {table}")


def _quote_ident(name: str, *, names_ok: list[str]) -> str:
    if name not in names_ok or not _IDENT.match(name):
        raise ValueError(f"Unknown column: {name}")
    return name


__all__ = [
    "MemoryLibraryStore",
    "SqlLibraryStore",
    "attach_library",
    "coerce_store",
]
