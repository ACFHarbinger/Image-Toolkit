"""Sidecar handlers for the scan capability (L-04 / #898)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.scan.commands import (
    MetadataItemCommand,
    SaveMetadataCommand,
    ScanDirectoryCommand,
    SuggestTagsCommand,
)
from middleware.src.services.scan.service import ScanService


def handle_scan_directory(service: ScanService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch scan.directory onto ScanService."""
    svc = service or ScanService()
    formats_list = tuple(params.get("formats") or ("webp", "png", "jpg", "jpeg", "gif"))
    command = ScanDirectoryCommand(
        directory=params["directory"],
        recursive=bool(params.get("recursive", False)),
        formats=formats_list,
        max_results=int(params.get("max_results", 500)),
    )
    result = svc.scan_directory(command)
    return {
        "directory": result.directory,
        "total_found": result.total_found,
        "database_available": result.database_available,
        "images": [
            {
                "path": img.path,
                "filename": img.filename,
                "extension": img.extension,
                "size_bytes": img.size_bytes,
                "width": img.width,
                "height": img.height,
                "in_database": img.in_database,
                "tags": list(img.tags),
                "group_name": img.group_name,
                "subgroup_name": img.subgroup_name,
            }
            for img in result.images
        ],
    }


def handle_save_metadata(service: ScanService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch scan.save_metadata onto ScanService."""
    svc = service or ScanService()
    raw_items = params.get("items", [])
    items: list[MetadataItemCommand] = [
        MetadataItemCommand(
            path=item["path"],
            tags=tuple(item.get("tags") or ()),
            group_name=item.get("group_name"),
            subgroup_name=item.get("subgroup_name"),
        )
        for item in raw_items
    ]
    result = svc.save_metadata(SaveMetadataCommand(items=tuple(items)))
    return {
        "saved_count": result.saved_count,
        "success": result.success,
        "database_available": result.database_available,
        "errors": list(result.errors),
    }


def handle_suggest_tags(service: ScanService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch scan.suggest_tags onto ScanService."""
    svc = service or ScanService()
    raw_paths = tuple(params.get("paths", []))
    result = svc.suggest_tags(SuggestTagsCommand(paths=raw_paths))
    return {
        "suggestions": {k: list(v) for k, v in result.suggestions.items()},
    }


__all__ = [
    "handle_save_metadata",
    "handle_scan_directory",
    "handle_suggest_tags",
]
