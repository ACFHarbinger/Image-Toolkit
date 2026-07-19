"""PgvectorImageDatabase-compatible facade over the unified DAL (DB.6).

The image tabs (Search / Scan and Tag / preview window / wallpaper display)
were written against ``PgvectorImageDatabase``'s method surface via
``db_tab_ref.db``. This facade reproduces that exact surface on top of the
session-keyed library store, so those tabs port without touching their call
sites — only the DatabaseTab stops owning a Postgres connection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .image_repo import ImageRepo
from .maintenance import Maintenance
from .search_repo import SearchRepo
from .tag_repo import TagRepo


class UnifiedImageDatabase:
    """Drop-in replacement for PgvectorImageDatabase, backed by library.db."""

    def __init__(self, db):
        self._db = db
        self._images = ImageRepo(db)
        self._tags = TagRepo(db)
        self._search = SearchRepo(db)
        self._maintenance = Maintenance(db)

    # ---- images -------------------------------------------------------

    def add_image(self, file_path: str, embedding=None, group_name=None,
                  subgroup_name=None, tags=None, width=None, height=None) -> int:
        return self._images.add_image(
            file_path, embedding=embedding, group_name=group_name,
            subgroup_name=subgroup_name, tags=tags, width=width, height=height,
        )

    def update_image(self, image_id: int, group_name=None, subgroup_name=None,
                     tags=None) -> None:
        self._images.update_image(
            image_id, group_name=group_name, subgroup_name=subgroup_name,
            tags=tags,
        )

    def delete_image(self, image_id: int) -> None:
        self._images.delete_image(image_id)

    def get_image_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        return self._images.get_image_by_path(file_path)

    def paths_in_db(self, paths: List[str]) -> set:
        return self._images.paths_in_db(paths)

    def get_image_tags(self, image_id: int) -> List[str]:
        return self._images.get_image_tags(image_id)

    def search_images(self, **query_params) -> List[Dict[str, Any]]:
        # Legacy callers pass query_vector=None; the unified path has no
        # dead pgvector column — semantic search arrives via SearchRepo
        # (DB.7), not through this parameter.
        query_params.pop("query_vector", None)
        return self._search.search_images(**query_params)

    def update_phash(self, image_id: int, phash_int: int) -> None:
        self._images.update_phash(image_id, phash_int)

    # ---- groups / subgroups --------------------------------------------

    def add_group(self, name: str) -> None:
        self._images.add_group(name)

    def add_subgroup(self, name: str, group_name: str) -> None:
        self._images.add_subgroup(name, group_name)

    def delete_group(self, name: str) -> None:
        self._images.delete_group(name)

    def delete_subgroup(self, name: str, group_name: str) -> None:
        self._images.delete_subgroup(name, group_name)

    def rename_group(self, old_name: str, new_name: str) -> None:
        self._images.rename_group(old_name, new_name)

    def rename_subgroup(self, old_name: str, new_name: str, group_name: str) -> None:
        self._images.rename_subgroup(old_name, new_name, group_name)

    def get_all_groups(self, limit: int = 10000) -> List[str]:
        return self._images.get_all_groups()

    def get_all_subgroups(self, limit: int = 10000) -> List[str]:
        return self._images.get_all_subgroups()

    def get_subgroups_for_group(self, group_name: str, limit: int = 10000) -> List[str]:
        return self._images.get_subgroups_for_group(group_name)

    def get_all_subgroups_detailed(self, limit: int = 10000) -> List[Tuple[str, str]]:
        return self._images.get_all_subgroups_detailed()

    # ---- tags -----------------------------------------------------------

    def add_tag(self, name: str, type: Optional[str] = None) -> None:  # noqa: A002
        self._tags.add_tag(name, type)

    def delete_tag(self, name: str) -> None:
        self._tags.delete_tag(name)

    def rename_tag(self, old_name: str, new_name: str) -> None:
        self._tags.rename_tag(old_name, new_name)

    def update_tag_type(self, name: str, new_type: Optional[str]) -> None:
        self._tags.update_tag_type(name, new_type)

    def get_all_tags(self, limit: int = 10000) -> List[str]:
        return self._tags.get_all_tags()

    def get_all_tags_with_types(self, limit: int = 10000) -> List[Dict[str, str]]:
        return self._tags.get_all_tags_with_types()

    # ---- maintenance -----------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        return self._maintenance.statistics()

    def maintenance_vacuum(self, full: bool = False) -> None:
        self._maintenance.vacuum()

    def maintenance_reindex(self) -> None:
        self._maintenance.reindex()

    def reset_database(self) -> None:
        """Wipe all rows. Refuses without a verified backup manifest."""
        self._maintenance.reset_database()

    def close(self) -> None:
        """No-op: the session Database outlives any one consumer; it is
        closed at logout via session.close_session()."""
