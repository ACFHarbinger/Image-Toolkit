"""Library listings differential: the store's legacy row shape vs the
service's contract record (L-02 / #896, #883 harness).

Both sides read the same seeded unified store: the legacy side projects
``UnifiedImageDatabase.search_files`` exactly as the Qt/GUI tabs consume
it (the Rust ``db.rs`` surface this capability replaces for L-07 #901),
the service side projects ``list_images_result``. The projection is the
filename list plus tag membership — ids and timestamps are not compared.
"""

from __future__ import annotations

from pathlib import Path

from middleware.src.services.library import list_images_result


def pair(tmp: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Return ``(legacy, service)`` projections for one seeded store."""
    import backend
    from middleware.src.database.unified import session
    from middleware.src.database.unified.facade import UnifiedImageDatabase

    handle = backend.database.Database(str(tmp / "lib.db"), "pw", "salt")
    try:
        session.ensure_schema(handle)
        store = UnifiedImageDatabase(handle)
        _seed(store, tmp)
        return _legacy(store), _service(store)
    finally:
        handle.close()


def _seed(store, tmp: Path) -> None:
    for name, group, sub, tags in (
        ("a.png", "Trips", "Beach", ["sunset"]),
        ("b.jpg", "Trips", None, ["night"]),
    ):
        path = tmp / name
        path.write_bytes(b"x")
        store.add_image(str(path), embedding=None, group_name=group,
                        subgroup_name=sub, tags=tags, width=10, height=10)


def _legacy(store) -> dict[str, object]:
    rows = store.search_files(group_name="Trips", tags=[], input_formats=None, limit=10000)
    return {
        "filenames": sorted(row["filename"] for row in rows),
        "tagged_night": sorted(row["filename"] for row in rows if "night" in row["tags"]),
    }


def _service(store) -> dict[str, object]:
    result = list_images_result(store, {"group_name": "Trips"})
    return {
        "filenames": sorted(image["filename"] for image in result["images"]),
        "tagged_night": sorted(
            image["filename"] for image in result["images"] if "night" in (image.get("tags") or [])
        ),
    }
