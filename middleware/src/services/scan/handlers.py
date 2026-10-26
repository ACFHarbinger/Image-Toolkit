"""Command handlers for the Scan & Tag service (L-04 / #898, Issue #881)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Sequence

from middleware.src.services.base import CommandValidationError, Handler
from middleware.src.services.scan.commands import (
    MetadataItemCommand,
    SaveMetadataCommand,
    SaveMetadataResult,
    ScanDirectoryCommand,
    ScanDirectoryResult,
    ScannedImageRecord,
    SuggestTagsCommand,
    SuggestTagsResult,
)

_WORD_RE = re.compile(r"[A-Za-z0-9]{2,}")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "img",
        "image",
        "pic",
        "photo",
        "scan",
        "new",
        "copy",
        "temp",
        "tmp",
        "download",
        "downloads",
        "raw",
        "edit",
    }
)


def _explicit_assignment(group_name: str | None, subgroup_name: str | None) -> tuple[str, str]:
    """Blank clears the column. A cleared group cannot keep a subgroup."""
    group = group_name.strip() if isinstance(group_name, str) else ""
    subgroup = subgroup_name.strip() if isinstance(subgroup_name, str) else ""
    if not group:
        subgroup = ""
    return group, subgroup


def _extract_path_tokens(path_str: str) -> tuple[str, ...]:
    path = Path(path_str)
    tokens: list[str] = []
    # Immediate parent directory words
    if path.parent.name:
        tokens.extend(
            w.lower() for w in _WORD_RE.findall(path.parent.name) if len(w) >= 2 and w.lower() not in _STOPWORDS
        )
    # Filename stem words
    tokens.extend(w.lower() for w in _WORD_RE.findall(path.stem) if len(w) >= 2 and w.lower() not in _STOPWORDS)
    # Grandparent directory words
    if path.parent.parent.name and len(tokens) < 6:
        tokens.extend(
            w.lower() for w in _WORD_RE.findall(path.parent.parent.name) if len(w) >= 2 and w.lower() not in _STOPWORDS
        )
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return tuple(result[:8])


class ScanDirectoryHandler(Handler[ScanDirectoryCommand, ScanDirectoryResult]):
    """Recursively or flatly scans a directory for image files and probes metadata."""

    def __init__(self, db_session: Any | None = None) -> None:
        self._db_session = db_session

    def handle(self, command: ScanDirectoryCommand) -> ScanDirectoryResult:
        dir_path = Path(command.directory)
        if not dir_path.exists() or not dir_path.is_dir():
            raise CommandValidationError(
                f"Directory not found or not a directory: {command.directory}", field="directory"
            )

        normalized_formats = {
            fmt.lower().lstrip(".") for fmt in (command.formats or ("webp", "png", "jpg", "jpeg", "gif"))
        }

        discovered_paths: list[Path] = []
        self._walk_dir(dir_path, discovered_paths, normalized_formats, command.recursive, command.max_results)

        db_known_paths = self._query_db_paths(discovered_paths) if self._db_session is not None else set()

        records: list[ScannedImageRecord] = []
        for path in discovered_paths:
            try:
                stat = path.stat()
                size_bytes = stat.st_size
            except OSError:
                continue

            width: int | None = None
            height: int | None = None
            try:
                from PIL import Image

                with Image.open(path) as img:
                    width, height = img.size
            except Exception:
                pass

            str_path = str(path.resolve())
            records.append(
                ScannedImageRecord(
                    path=str_path,
                    filename=path.name,
                    extension=path.suffix.lower().lstrip("."),
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    in_database=str_path in db_known_paths or str(path) in db_known_paths,
                    group_name=path.parent.name if path.parent != dir_path else None,
                )
            )

        return ScanDirectoryResult(
            directory=str(dir_path.resolve()),
            total_found=len(records),
            images=tuple(records),
            database_available=self._db_session is not None,
        )

    def _walk_dir(
        self,
        current_dir: Path,
        collected: list[Path],
        valid_exts: set[str],
        recursive: bool,
        limit: int,
    ) -> None:
        try:
            with os.scandir(current_dir) as entries:
                subdirs: list[Path] = []
                for entry in entries:
                    if len(collected) >= limit:
                        return
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_file(follow_symlinks=False):
                            ext = Path(entry.name).suffix.lower().lstrip(".")
                            if ext in valid_exts:
                                collected.append(Path(entry.path))
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            subdirs.append(Path(entry.path))
                    except OSError:
                        continue
                if recursive:
                    for subdir in subdirs:
                        if len(collected) >= limit:
                            break
                        self._walk_dir(subdir, collected, valid_exts, recursive, limit)
        except (PermissionError, OSError):
            return

    def _query_db_paths(self, paths: Sequence[Path]) -> set[str]:
        if self._db_session is None:
            return set()
        str_paths = [str(p.resolve()) for p in paths]
        known = getattr(self._db_session, "paths_in_db", None)
        if callable(known):
            return set(known(str_paths))
        listed = getattr(self._db_session, "filter_known_paths", None)
        if callable(listed):
            return set(listed(str_paths))
        try:
            from middleware.src.database.unified.image_repo import ImageRepo

            repo = ImageRepo(self._db_session)
            if hasattr(repo, "filter_known_paths"):
                return set(repo.filter_known_paths(str_paths))
            # Fallback simple check
            known: set[str] = set()
            for p in str_paths:
                if hasattr(repo, "get_image_by_path") and repo.get_image_by_path(p):
                    known.add(p)
            return known
        except Exception:
            return set()


class SaveMetadataHandler(Handler[SaveMetadataCommand, SaveMetadataResult]):
    """Persists metadata and tags for scanned images into the library database."""

    def __init__(self, db_session: Any | None = None) -> None:
        self._db_session = db_session

    def handle(self, command: SaveMetadataCommand) -> SaveMetadataResult:
        if self._db_session is None:
            return SaveMetadataResult(
                saved_count=0,
                success=False,
                database_available=False,
                errors=("Database session unavailable (vault locked or offline)",),
            )

        saved = 0
        errors: list[str] = []
        for item in command.items:
            try:
                image_id = self._write_item(item)
            except Exception as exc:
                errors.append(f"Failed to save {item.path}: {exc}")
                continue
            if image_id is None:
                errors.append(f"Failed to save {item.path}: write did not complete")
                continue
            saved += 1

        return SaveMetadataResult(
            saved_count=saved,
            success=len(errors) == 0 and saved == len(command.items),
            database_available=True,
            errors=tuple(errors),
        )

    def _write_item(self, item: MetadataItemCommand) -> int | None:
        """Update an existing row in place. A new path still goes through ``add_image``."""
        writer = getattr(self._db_session, "add_image", None)
        if callable(writer):
            existing = self._stored_image(item.path)
            if existing is not None:
                return self._update_existing(existing, item)
            return writer(
                item.path,
                group_name=item.group_name,
                subgroup_name=item.subgroup_name,
                tags=list(item.tags),
            )
        from middleware.src.database.unified.image_repo import ImageRepo

        repo = ImageRepo(self._db_session)
        existing = repo.get_image_by_path(item.path) if callable(getattr(repo, "get_image_by_path", None)) else None
        if isinstance(existing, dict) and "id" in existing:
            return self._update_existing(existing, item, repo.update_image)
        return repo.add_image(
            item.path,
            group_name=item.group_name,
            subgroup_name=item.subgroup_name,
            tags=list(item.tags),
        )

    def _stored_image(self, path: str) -> dict[str, Any] | None:
        getter = getattr(self._db_session, "get_image_by_path", None)
        if not callable(getter):
            return None
        found = getter(path)
        if not isinstance(found, dict) or "id" not in found:
            return None
        return found

    def _update_existing(
        self,
        existing: dict[str, Any],
        item: MetadataItemCommand,
        updater: Any = None,
    ) -> int:
        group, subgroup = _explicit_assignment(item.group_name, item.subgroup_name)
        image_id = int(existing["id"])
        if updater is None:
            updater = getattr(self._db_session, "update_image", None)
        if not callable(updater):
            raise RuntimeError("store does not support update_image")
        updater(image_id, group_name=group, subgroup_name=subgroup, tags=list(item.tags))
        return image_id


class SuggestTagsHandler(Handler[SuggestTagsCommand, SuggestTagsResult]):
    """Generates heuristic tag suggestions from image paths and folder structure."""

    def handle(self, command: SuggestTagsCommand) -> SuggestTagsResult:
        suggestions: dict[str, tuple[str, ...]] = {}
        for path_str in command.paths:
            suggestions[path_str] = _extract_path_tokens(path_str)
        return SuggestTagsResult(suggestions=suggestions)
