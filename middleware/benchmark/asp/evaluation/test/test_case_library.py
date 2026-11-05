"""User case-library subsets and extra case directories."""

from __future__ import annotations

import json

import pytest

from middleware.benchmark.asp.evaluation.other.case_library import (
    add_directory,
    cases_in_directory,
    delete_subset,
    list_directories,
    list_user_subsets,
    load_store,
    remove_directory,
    resolve_case_file,
    selectable_subsets,
    store_path,
    upsert_subset,
)
from middleware.benchmark.asp.slices import SMOKE_SET_V1, get_slice, get_slice_cases


@pytest.fixture(autouse=True)
def asp_eval_library(tmp_path, monkeypatch):
    path = tmp_path / "library.json"
    monkeypatch.setenv("ASP_EVAL_LIBRARY", str(path))
    return path


def _touch(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")


def test_load_missing_store_is_empty(asp_eval_library):
    assert store_path() == asp_eval_library
    assert not asp_eval_library.exists()
    assert load_store() == {"subsets": [], "directories": []}
    assert not asp_eval_library.exists()


def test_upsert_list_replace_delete(asp_eval_library):
    created = upsert_subset(
        " daily ",
        [" asp_test04 ", "asp_test04", "asp_test08", ""],
        description="first",
    )
    assert created == {
        "name": "daily",
        "description": "first",
        "tags": [],
        "case_ids": ["asp_test04", "asp_test08"],
    }
    assert list_user_subsets() == [created]

    upsert_subset("weekly", ["asp_test09"])
    replaced = upsert_subset("daily", ["asp_test27"], description="second")
    listed = list_user_subsets()
    assert [row["name"] for row in listed] == ["daily", "weekly"]
    assert listed[0] == replaced
    assert listed[0]["case_ids"] == ["asp_test27"]

    saved = json.loads(asp_eval_library.read_text(encoding="utf-8"))
    assert saved["subsets"][0]["case_ids"] == ["asp_test27"]
    assert saved["directories"] == []

    assert delete_subset(" daily ") is True
    assert [row["name"] for row in list_user_subsets()] == ["weekly"]
    assert delete_subset("daily") is False
    assert delete_subset("missing") is False

    with pytest.raises(ValueError):
        upsert_subset("   ", ["asp_test04"])


def test_tag_normalization():
    saved = upsert_subset(
        "daily",
        ["asp_test04"],
        tags=[" Seam ", "SEAM", "ghost", " Ghost ", ""],
    )
    assert saved["tags"] == ["seam", "ghost"]
    assert list_user_subsets()[0]["tags"] == ["seam", "ghost"]


def test_cases_in_directory_and_resolve(tmp_path):
    root = tmp_path / "corpus"
    _touch(root / "output" / "clipA_anime_stitch.png")
    _touch(root / "clipA.png")
    _touch(root / "extra_case" / "panorama.png")
    _touch(root / "extra_case" / "baseline.png")
    _touch(root / "from_base" / "baseline.png")
    _touch(root / "from_stitch" / "stitch.png")
    _touch(root / "shot.png")
    _touch(root / ".hidden.png")
    _touch(root / "notes.txt")
    (root / "empty_dir").mkdir()

    assert cases_in_directory(str(root)) == [
        "clipA",
        "extra_case",
        "from_base",
        "from_stitch",
        "shot",
    ]
    output = root / "output" / "clipA_anime_stitch.png"
    assert resolve_case_file(str(root), "clipA") == str(output)
    assert resolve_case_file(str(root), "extra_case") == str(root / "extra_case" / "panorama.png")
    assert resolve_case_file(str(root), "from_base") == str(root / "from_base" / "baseline.png")
    assert resolve_case_file(str(root), "from_stitch") == str(root / "from_stitch" / "stitch.png")
    assert resolve_case_file(str(root), "shot") == str(root / "shot.png")
    assert resolve_case_file(str(root), "missing") is None


def test_add_directory_rejects_missing_and_replaces_label(tmp_path):
    missing = tmp_path / "no-such-dir"
    with pytest.raises(FileNotFoundError):
        add_directory(str(missing))
    a_file = tmp_path / "not-a-dir.png"
    a_file.write_bytes(b"png")
    with pytest.raises(FileNotFoundError):
        add_directory(str(a_file))

    present = tmp_path / "clips"
    present.mkdir()
    added = add_directory(str(present), label="clips")
    assert added == {"path": str(present.resolve()), "label": "clips"}
    assert list_directories() == [added]

    renamed = add_directory(str(present), label="renamed")
    assert list_directories() == [{"path": str(present.resolve()), "label": "renamed"}]
    assert renamed["label"] == "renamed"

    assert remove_directory(str(present)) is True
    assert list_directories() == []
    assert remove_directory(str(present)) is False


def test_get_slice_user_subset_builtin_and_unknown():
    upsert_subset("daily", ["asp_test04"], description="seam day", tags=["Seam"])
    found = get_slice("daily")
    assert found.name == "daily"
    assert found.version == "user"
    assert found.description == "seam day"
    assert list(found.case_ids) == ["asp_test04"]
    assert found.metadata["tags"] == ["seam"]
    assert list(get_slice_cases("daily")) == ["asp_test04"]

    folded = get_slice("Daily")
    assert folded.name == "daily"
    assert folded.version == "user"
    assert list(folded.case_ids) == ["asp_test04"]

    with pytest.raises(KeyError, match="no-such-slice-zz"):
        get_slice("no-such-slice-zz")

    upsert_subset("smoke", ["not-a-real-case"])
    assert get_slice("smoke") == SMOKE_SET_V1


def test_selectable_subsets_builtin_then_user():
    upsert_subset("daily", ["asp_test04"], description="d", tags=["seam"])
    rows = selectable_subsets()
    builtin = [row["name"] for row in rows if row["kind"] == "builtin"]
    assert builtin == ["asp_dev_v1", "smoke_v1", "structural_red_v1"]
    assert [row["kind"] for row in rows] == ["builtin", "builtin", "builtin", "user"]
    assert rows[-1] == {
        "kind": "user",
        "name": "daily",
        "description": "d",
        "tags": ["seam"],
        "case_ids": ["asp_test04"],
    }
    smoke = next(row for row in rows if row["name"] == "smoke_v1")
    assert smoke["case_ids"] == list(SMOKE_SET_V1.case_ids)
