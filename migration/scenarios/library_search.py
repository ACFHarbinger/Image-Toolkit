"""Library image-search differential: the store's legacy search surface vs
the service projection with pattern/format filters (L-03 / #897, #883
harness). The legacy side is the exact ``search_files`` call shape the
retired Rust-invoke SearchTab sent (``db.rs`` duplicate, retired by
L-07 #901); the service side is ``list_images_result`` with the same
filters. The projection is the filename list.
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
    for name, group, tags in (
        ("portrait.png", "Studio", ["sunset"]),
        ("landscape.jpg", "Studio", ["night"]),
        ("sketch.png", "Trips", ["night"]),
    ):
        path = tmp / name
        path.write_bytes(b"x")
        store.add_image(str(path), embedding=None, group_name=group,
                        subgroup_name=None, tags=tags, width=10, height=10)


def _legacy(store) -> dict[str, object]:
    rows = store.search_files(filename_pattern="portrait", tags=[], input_formats=["png"], limit=10000)
    return {"filenames": sorted(row["filename"] for row in rows)}


def _service(store) -> dict[str, object]:
    result = list_images_result(store, {"filename_pattern": "portrait", "input_formats": ["png"]})
    return {"filenames": sorted(image["filename"] for image in result["images"])}
