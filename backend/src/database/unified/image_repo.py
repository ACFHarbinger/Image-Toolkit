"""Image index repository — DB.3 / DB.6.

Mirrors PgvectorImageDatabase's method names (`add_image`,
`get_image_by_path`, `update_image`, `add_group`, `get_all_subgroups_detailed`,
…) so the image-tab port is mostly an import swap. Groups/subgroups are FKs
here (the Postgres schema duplicated them as text columns on images).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._util import transaction
from .tag_repo import TagRepo

_IMAGE_COLUMNS = (
    "id", "file_path", "filename", "file_size", "width", "height", "phash",
    "group_id", "subgroup_id", "date_added", "date_modified",
)

_SELECT_IMAGE = (
    "SELECT i.id, i.file_path, i.filename, i.file_size, i.width, i.height, "
    "i.phash, i.group_id, i.subgroup_id, i.date_added, i.date_modified, "
    "g.name AS group_name, s.name AS subgroup_name "
    "FROM images i "
    "LEFT JOIN groups g ON g.id = i.group_id "
    "LEFT JOIN subgroups s ON s.id = i.subgroup_id "
)


class ImageRepo:
    def __init__(self, db):
        self._db = db
        self._tags = TagRepo(db)

    # ------------------------------------------------------------------
    # Groups / subgroups (PgvectorImageDatabase parity)
    # ------------------------------------------------------------------

    def add_group(self, name: str) -> int:
        if not name or not name.strip():
            raise ValueError("Group name cannot be empty")
        name = name.strip()
        self._db.execute(
            "INSERT OR IGNORE INTO groups (name) VALUES (?)", (name,)
        )
        return self._db.query(
            "SELECT id FROM groups WHERE name = ?", (name,)
        )[0][0]

    def add_subgroup(self, name: str, group_name: str) -> int:
        if not name or not name.strip() or not group_name or not group_name.strip():
            raise ValueError("Subgroup name and Group name cannot be empty")
        group_id = self.add_group(group_name)
        name = name.strip()
        self._db.execute(
            "INSERT OR IGNORE INTO subgroups (name, group_id) VALUES (?, ?)",
            (name, group_id),
        )
        return self._db.query(
            "SELECT id FROM subgroups WHERE name = ? AND group_id = ?",
            (name, group_id),
        )[0][0]

    def delete_group(self, name: str) -> None:
        """Subgroups cascade; images keep their rows (group_id SET NULL)."""
        self._db.execute("DELETE FROM groups WHERE name = ?", (name,))

    def delete_subgroup(self, name: str, group_name: str) -> None:
        self._db.execute(
            "DELETE FROM subgroups WHERE name = ? AND group_id = "
            "(SELECT id FROM groups WHERE name = ?)",
            (name, group_name),
        )

    def rename_group(self, old_name: str, new_name: str) -> None:
        if not new_name or not new_name.strip():
            raise ValueError("Group name cannot be empty")
        changed = self._db.execute(
            "UPDATE groups SET name = ? WHERE name = ?",
            (new_name.strip(), old_name),
        )
        if changed == 0:
            raise KeyError(f"group not found: {old_name}")

    def rename_subgroup(self, old_name: str, new_name: str, group_name: str) -> None:
        if not new_name or not new_name.strip():
            raise ValueError("Subgroup name cannot be empty")
        changed = self._db.execute(
            "UPDATE subgroups SET name = ? WHERE name = ? AND group_id = "
            "(SELECT id FROM groups WHERE name = ?)",
            (new_name.strip(), old_name, group_name),
        )
        if changed == 0:
            raise KeyError(f"subgroup not found: {old_name} in {group_name}")

    def get_all_groups(self) -> List[str]:
        return [r[0] for r in self._db.query(
            "SELECT name FROM groups ORDER BY name", ()
        )]

    def get_all_subgroups(self) -> List[str]:
        return [r[0] for r in self._db.query(
            "SELECT DISTINCT name FROM subgroups ORDER BY name", ()
        )]

    def get_subgroups_for_group(self, group_name: str) -> List[str]:
        return [r[0] for r in self._db.query(
            "SELECT s.name FROM subgroups s JOIN groups g ON g.id = s.group_id "
            "WHERE g.name = ? ORDER BY s.name",
            (group_name,),
        )]

    def get_all_subgroups_detailed(self) -> List[Tuple[str, str]]:
        """[(subgroup_name, group_name), ...] — parity with the legacy API."""
        return self._db.query(
            "SELECT s.name, g.name FROM subgroups s "
            "JOIN groups g ON g.id = s.group_id ORDER BY g.name, s.name",
            (),
        )

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def add_image(
        self,
        file_path: str,
        embedding: Optional[List[float]] = None,  # legacy-signature compat; unused
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> int:
        """Upsert an image row by absolute path; returns the image id.

        ``tags=None`` leaves existing tag links untouched; a list (possibly
        empty) replaces them — same semantics as the legacy backend.
        The legacy ``embedding`` parameter is accepted and ignored (real
        embeddings live in the ``embeddings`` table, DB.7).
        """
        path = Path(file_path)
        abs_path = str(path.absolute())
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        if file_size is None:
            try:
                file_size = path.stat().st_size
            except OSError:
                file_size = 0

        with transaction(self._db):
            group_id = (
                self.add_group(group_name)
                if group_name and group_name.strip() else None
            )
            subgroup_id = (
                self.add_subgroup(subgroup_name, group_name)
                if group_id is not None and subgroup_name and subgroup_name.strip()
                else None
            )

            self._db.execute(
                "INSERT INTO images (file_path, filename, file_size, width, "
                "height, group_id, subgroup_id, date_added, date_modified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(file_path) DO UPDATE SET "
                "filename=excluded.filename, file_size=excluded.file_size, "
                "width=COALESCE(excluded.width, images.width), "
                "height=COALESCE(excluded.height, images.height), "
                "group_id=COALESCE(excluded.group_id, images.group_id), "
                "subgroup_id=COALESCE(excluded.subgroup_id, images.subgroup_id), "
                "date_modified=excluded.date_modified",
                (abs_path, path.name, file_size, width, height,
                 group_id, subgroup_id, now, now),
            )
            image_id = self._db.query(
                "SELECT id FROM images WHERE file_path = ?", (abs_path,)
            )[0][0]

            if tags is not None:
                self._replace_image_tags(image_id, tags)
        return image_id

    def update_image(
        self,
        image_id: int,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Update the provided fields only (None = leave unchanged)."""
        with transaction(self._db):
            if group_name is not None:
                group_id = (
                    self.add_group(group_name) if group_name.strip() else None
                )
                self._db.execute(
                    "UPDATE images SET group_id = ? WHERE id = ?",
                    (group_id, image_id),
                )
            if subgroup_name is not None:
                if subgroup_name.strip():
                    row = self._db.query(
                        "SELECT g.name FROM images i JOIN groups g "
                        "ON g.id = i.group_id WHERE i.id = ?",
                        (image_id,),
                    )
                    if not row:
                        raise ValueError(
                            "cannot set a subgroup on an image without a group"
                        )
                    subgroup_id = self.add_subgroup(subgroup_name, row[0][0])
                else:
                    subgroup_id = None
                self._db.execute(
                    "UPDATE images SET subgroup_id = ? WHERE id = ?",
                    (subgroup_id, image_id),
                )
            if tags is not None:
                self._replace_image_tags(image_id, tags)
            self._db.execute(
                "UPDATE images SET date_modified = ? WHERE id = ?",
                (datetime.now().isoformat(sep=" ", timespec="seconds"), image_id),
            )

    def delete_image(self, image_id: int) -> bool:
        return self._db.execute(
            "DELETE FROM images WHERE id = ?", (image_id,)
        ) > 0

    def get_image_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        abs_path = str(Path(file_path).absolute())
        rows = self._db.query(
            _SELECT_IMAGE + "WHERE i.file_path = ?", (abs_path,)
        )
        if not rows:
            return None
        return self._assemble(rows[0])

    def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        rows = self._db.query(_SELECT_IMAGE + "WHERE i.id = ?", (image_id,))
        if not rows:
            return None
        return self._assemble(rows[0])

    def get_image_tags(self, image_id: int) -> List[str]:
        return [r[0] for r in self._db.query(
            "SELECT t.name FROM image_tags it JOIN tags t ON t.id = it.tag_id "
            "WHERE it.image_id = ? ORDER BY t.name",
            (image_id,),
        )]

    def paths_in_db(self, paths: List[str]) -> set:
        """Subset of *paths* already indexed (bulk 'is in DB?' check for the
        scan tab; one query per 500-path chunk instead of one per file)."""
        found: set = set()
        chunk = 500
        abs_paths = [str(Path(p).absolute()) for p in paths]
        for i in range(0, len(abs_paths), chunk):
            part = abs_paths[i:i + chunk]
            marks = ",".join("?" * len(part))
            rows = self._db.query(
                f"SELECT file_path FROM images WHERE file_path IN ({marks})",
                tuple(part),
            )
            found.update(r[0] for r in rows)
        return found

    def count(self) -> int:
        return self._db.query("SELECT count(*) FROM images", ())[0][0]

    # ---- pHash (dedup primitive only — see DB.7) ----------------------

    def update_phash(self, image_id: int, phash_int: int) -> None:
        self._db.execute(
            "UPDATE images SET phash = ? WHERE id = ?", (phash_int, image_id)
        )

    def get_all_phashes(self) -> List[Tuple[int, str, int]]:
        """[(id, file_path, phash), ...] for rows with a phash set."""
        return self._db.query(
            "SELECT id, file_path, phash FROM images WHERE phash IS NOT NULL",
            (),
        )

    # ------------------------------------------------------------------

    def _assemble(self, row: tuple) -> Dict[str, Any]:
        data = dict(zip(_IMAGE_COLUMNS + ("group_name", "subgroup_name"), row))
        data["tags"] = self.get_image_tags(data["id"])
        return data

    def _replace_image_tags(self, image_id: int, tags: List[str]) -> None:
        self._db.execute(
            "DELETE FROM image_tags WHERE image_id = ?", (image_id,)
        )
        for name in tags:
            if not name or not name.strip():
                continue
            tag_id = self._tags.get_or_create(name.strip())
            self._db.execute(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) "
                "VALUES (?, ?)",
                (image_id, tag_id),
            )
