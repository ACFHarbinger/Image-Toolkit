"""Library listings projection (L-02 / #896): the attached-store surface,
the unavailable path, and the record normalization the contract pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from middleware.src.services.library import (
    list_groups_result,
    list_images_result,
    list_tags_result,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import backend  # noqa: E402
from middleware.src.database.unified import session  # noqa: E402
from middleware.src.database.unified.facade import UnifiedImageDatabase  # noqa: E402


@pytest.fixture()
def store(tmp_path: Path) -> UnifiedImageDatabase:
    handle = backend.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    session.ensure_schema(handle)
    db = UnifiedImageDatabase(handle)
    for name, group, sub, tags in (
        ("a.png", "Trips", "Beach", ["sunset", "night"]),
        ("b.jpg", "Trips", None, ["night"]),
        ("c.png", "Studio", None, ["portrait"]),
    ):
        p = tmp_path / name
        p.write_bytes(b"x")
        db.add_image(str(p), embedding=None, group_name=group,
                     subgroup_name=sub, tags=tags, width=10, height=10)
    yield db
    handle.close()


def test_no_store_stays_unavailable() -> None:
    assert list_images_result(None, {}) == {"available": False, "images": []}
    assert list_tags_result(None) == {"available": False, "tags": []}
    assert list_groups_result(None) == {"available": False, "groups": []}


def test_list_images_returns_contract_records(store: UnifiedImageDatabase) -> None:
    result = list_images_result(store, {"group_name": "Trips"})
    assert result["available"] is True
    assert sorted(image["filename"] for image in result["images"]) == ["a.png", "b.jpg"]
    record = next(image for image in result["images"] if image["filename"] == "a.png")
    assert {"id", "file_path", "filename", "group_name", "subgroup_name", "tags"} <= set(record)
    assert record["group_name"] == "Trips"
    assert record["subgroup_name"] == "Beach"
    assert "date_added" in record and isinstance(record["date_added"], str)


def test_filters_match_the_search_files_surface(store: UnifiedImageDatabase) -> None:
    by_tag = list_images_result(store, {"tags": ["night"]})
    assert sorted(image["filename"] for image in by_tag["images"]) == ["a.png", "b.jpg"]

    by_pattern = list_images_result(store, {"filename_pattern": "c"})
    assert [image["filename"] for image in by_pattern["images"]] == ["c.png"]

    multi = list_images_result(store, {"group_names": ["Trips", "Studio"]})
    assert len(multi["images"]) == 3

    limited = list_images_result(store, {"limit": 1})
    assert len(limited["images"]) == 1


def test_limit_is_bounded(store: UnifiedImageDatabase) -> None:
    assert len(list_images_result(store, {"limit": 0})["images"]) == 3  # invalid -> default
    assert len(list_images_result(store, {"limit": 99_999_999})["images"]) == 3  # capped


def test_tags_and_groups_results(store: UnifiedImageDatabase) -> None:
    tags = list_tags_result(store)
    assert tags["available"] is True
    assert sorted(tags["tags"]) == ["night", "portrait", "sunset"]

    groups = list_groups_result(store)
    assert groups["available"] is True
    names = [group["name"] for group in groups["groups"]]
    assert names == sorted(names)
    trips = next(group for group in groups["groups"] if group["name"] == "Trips")
    assert trips["subgroups"] == ["Beach"]
    studio = next(group for group in groups["groups"] if group["name"] == "Studio")
    assert studio["subgroups"] == []
