"""Library stores attach only from an already-open session (#1108).

The default path ``~/.image-toolkit/library.db`` is never opened. A missing
session stays unavailable. Writes that do not land are errors.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from middleware.src.services.library.attach import MemoryLibraryStore, attach_library
from middleware.src.services.library.listings import list_images_result
from middleware.src.services.library_admin.admin import browse_result, catalog_result, mutate_result
from middleware.src.sidecar.handlers.scan import handle_save_metadata
from middleware.src.sidecar.server import SidecarServer


def _home_db() -> Path:
    return Path.home() / ".image-toolkit" / "library.db"


def test_missing_session_stays_unavailable_and_does_not_open_the_home_library(monkeypatch) -> None:
    def _refuse(*_args, **_kwargs):
        raise AssertionError("open_session must not run")

    monkeypatch.setattr("middleware.src.database.unified.session.open_session", _refuse)
    before = _home_db().stat().st_mtime if _home_db().exists() else None
    server = SidecarServer(stdout=io.StringIO(), library_store=object(), library_admin_store=object())
    attach_library(server, None)
    assert server.library_store is None
    assert server.library_admin_store is None
    assert server.scan_service is None
    assert list_images_result(server.library_store, {})["available"] is False
    assert catalog_result(server.library_admin_store)["available"] is False
    saved = handle_save_metadata(server.scan_service, {"items": [{"path": "/tmp/missing.png", "tags": ["night"]}]})
    assert saved["success"] is False
    assert saved["saved_count"] == 0
    assert saved["database_available"] is False
    assert saved["errors"]
    after = _home_db().stat().st_mtime if _home_db().exists() else None
    assert before == after


def test_live_vault_opens_the_library_handle_and_memory_store_does_not(monkeypatch) -> None:
    monkeypatch.setattr("middleware.src.services.library.attach._database_importable", lambda: True)
    opened: list[tuple[object, ...]] = []
    closed: list[bool] = []
    handle = object()

    def _open(*args: object, **_kwargs: object) -> object:
        opened.append(args)
        return handle

    def _close() -> None:
        closed.append(True)

    monkeypatch.setattr("middleware.src.database.unified.session.open_session", _open)
    monkeypatch.setattr("middleware.src.database.unified.session.close_session", _close)
    seen: list[object] = []

    class _Facade:
        def __init__(self, db: object) -> None:
            seen.append(db)
            self._db = db

    monkeypatch.setattr("middleware.src.database.unified.facade.UnifiedImageDatabase", _Facade)

    class _Manager:
        keystore_pass = "vault-secret"

    class _Vault:
        open = True
        account = "ada"
        _manager = _Manager()

    vault = _Vault()
    server = SidecarServer(stdout=io.StringIO())
    server.bind_vault_session(vault)
    assert opened == [("vault-secret", "ada")]
    assert seen == [handle]
    assert server.library_store._facade._db is handle
    assert server.library_store._raw is not vault
    assert closed == []
    server.clear_vault_session()
    assert closed == [True]
    assert server.library_store is None
    assert server.vault_session is None

    server.bind_vault_session(MemoryLibraryStore())
    assert opened == [("vault-secret", "ada")]
    assert closed == [True]
    assert isinstance(server.library_store, MemoryLibraryStore)
    server.clear_vault_session()
    assert closed == [True]
    assert server.library_store is None


def test_resave_replaces_group_and_clears_subgroup() -> None:
    store = MemoryLibraryStore()
    server = SidecarServer(stdout=io.StringIO(), library_session=store)
    path = "/tmp/redo3-library/shot.png"
    first = handle_save_metadata(
        server.scan_service,
        {"items": [{"path": path, "tags": ["night"], "group_name": "Trips", "subgroup_name": "Beach"}]},
    )
    assert first["success"] is True
    second = handle_save_metadata(
        server.scan_service,
        {"items": [{"path": path, "tags": ["night"], "group_name": "Studio", "subgroup_name": None}]},
    )
    assert second["success"] is True
    image = list_images_result(server.library_store, {})["images"][0]
    assert image["group_name"] == "Studio"
    assert not image["subgroup_name"]
    third = handle_save_metadata(
        server.scan_service,
        {"items": [{"path": path, "tags": ["night"], "group_name": None, "subgroup_name": None}]},
    )
    assert third["success"] is True
    image = list_images_result(server.library_store, {})["images"][0]
    assert not image["group_name"]
    assert not image["subgroup_name"]


def test_handler_clears_subgroup_when_the_group_changes(tmp_path: Path) -> None:
    backend = pytest.importorskip("backend")
    if not hasattr(backend, "database"):
        pytest.skip("backend.database is not importable")
    from middleware.src.database.unified import session
    from middleware.src.database.unified.image_repo import ImageRepo

    handle = backend.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    try:
        session.ensure_schema(handle)
        path = tmp_path / "shot.png"
        path.write_bytes(b"png")
        ImageRepo(handle).add_image(str(path), group_name="A", subgroup_name="Old", tags=["night"])
        server = SidecarServer(stdout=io.StringIO())
        attach_library(server, handle)
        saved = handle_save_metadata(
            server.scan_service,
            {"items": [{"path": str(path), "tags": ["night"], "group_name": "B", "subgroup_name": None}]},
        )
        assert saved["success"] is True
        row = ImageRepo(handle).get_image_by_path(str(path))
        assert row is not None
        assert row["group_name"] == "B"
        assert not row["subgroup_name"]
        assert row["subgroup_name"] != "Old"
    finally:
        handle.close()


def test_vault_session_bind_and_clear_control_library_stores() -> None:
    server = SidecarServer(stdout=io.StringIO())
    assert server.library_store is None
    store = MemoryLibraryStore()
    server.bind_vault_session(store)
    assert server.vault_session is store
    assert server.library_store is store
    server.clear_vault_session()
    assert server.vault_session is None
    assert server.library_store is None
    assert server.library_admin_store is None
    assert server.scan_service is None


def test_memory_store_write_is_readable_and_a_missing_rename_is_an_error() -> None:
    store = MemoryLibraryStore()
    server = SidecarServer(stdout=io.StringIO(), library_session=store)
    path = "/tmp/redo3-library/shot.png"
    saved = handle_save_metadata(
        server.scan_service,
        {"items": [{"path": path, "tags": ["night"], "group_name": "Trips", "subgroup_name": "Beach"}]},
    )
    assert saved == {
        "saved_count": 1,
        "success": True,
        "database_available": True,
        "errors": [],
    }
    listed = list_images_result(server.library_store, {"filename_pattern": "shot", "tags": ["night"]})
    assert listed["available"] is True
    assert listed["images"][0]["filename"] == "shot.png"
    assert listed["images"][0]["group_name"] == "Trips"
    assert listed["images"][0]["subgroup_name"] == "Beach"
    assert "night" in listed["images"][0]["tags"]
    page = browse_result(
        server.library_admin_store,
        {"table": "images", "limit": 10, "offset": 0, "column": "filename", "equals": "shot.png"},
    )
    assert page["error"] == ""
    assert page["row_count"] == 1
    renamed = mutate_result(
        server.library_admin_store,
        {"action": "rename_group", "name": "Trips", "destination": "Travel"},
    )
    assert renamed == {"available": True, "applied": 1, "error": ""}
    assert list_images_result(server.library_store, {})["images"][0]["group_name"] == "Travel"
    removed = mutate_result(server.library_admin_store, {"action": "delete_image", "name": path})
    assert removed["applied"] == 1
    assert list_images_result(server.library_store, {})["images"] == []
    missing = mutate_result(server.library_admin_store, {"action": "delete_image", "name": path})
    assert missing["applied"] == 0
    assert missing["error"] == "image not found"


def test_store_without_rename_does_not_report_success() -> None:
    class _Bare:
        def search_files(self, **_query):
            return []

        def browse_page(self, *_args, **_kwargs):
            return [], [], 0

        def add_group(self, _name):
            return None

        def get_all_groups(self):
            return []

        def get_all_subgroups_detailed(self):
            return []

        def get_all_tags_with_categories(self):
            return []

        def list_tables(self):
            return []

    result = mutate_result(_Bare(), {"action": "rename_group", "name": "Trips", "destination": "Travel"})
    assert result["available"] is True
    assert result["applied"] == 0
    assert "does not support" in result["error"]


def test_session_handle_calls_unified_image_database(monkeypatch) -> None:
    """A handle is wrapped by the real constructor even when the test spies it."""
    monkeypatch.setattr("middleware.src.services.library.attach._database_importable", lambda: True)

    def _refuse(*_args, **_kwargs):
        raise AssertionError("open_session must not run")

    monkeypatch.setattr("middleware.src.database.unified.session.open_session", _refuse)
    seen: list[object] = []

    class _Facade:
        def __init__(self, db: object) -> None:
            seen.append(db)
            self._db = db

    monkeypatch.setattr("middleware.src.database.unified.facade.UnifiedImageDatabase", _Facade)
    handle = object()
    server = SidecarServer(stdout=io.StringIO())
    attach_library(server, handle)
    assert seen == [handle]
    assert server.library_store._facade._db is handle
    assert server.library_admin_store is server.library_store
    assert server.scan_service is not None


def test_native_session_handle_uses_the_real_constructor(tmp_path: Path, monkeypatch) -> None:
    backend = pytest.importorskip("backend")
    if not hasattr(backend, "database"):
        pytest.skip("backend.database is not importable")
    from middleware.src.database.unified import session
    from middleware.src.database.unified.facade import UnifiedImageDatabase

    created: list[object] = []
    real = UnifiedImageDatabase

    def _spy(handle):
        created.append(handle)
        return real(handle)

    monkeypatch.setattr("middleware.src.database.unified.facade.UnifiedImageDatabase", _spy)
    monkeypatch.setattr("middleware.src.database.unified.session.open_session", _spy)
    handle = backend.database.Database(str(tmp_path / "lib.db"), "pw", "salt")
    try:
        session.ensure_schema(handle)
        server = SidecarServer(stdout=io.StringIO())
        attach_library(server, handle)
        assert created == [handle]
        path = tmp_path / "shot.png"
        path.write_bytes(b"png")
        saved = handle_save_metadata(
            server.scan_service,
            {"items": [{"path": str(path), "tags": ["night"], "group_name": "Trips"}]},
        )
        assert saved["success"] is True
        assert saved["saved_count"] == 1
        listed = list_images_result(server.library_store, {"group_name": "Trips"})
        assert [image["filename"] for image in listed["images"]] == ["shot.png"]
        assert "night" in listed["images"][0]["tags"]
        page = browse_result(
            server.library_admin_store,
            {"table": "images", "limit": 5, "offset": 0, "column": "filename", "equals": "shot.png"},
        )
        assert page["row_count"] == 1
        assert page["error"] == ""
        rejected = browse_result(
            server.library_admin_store,
            {"table": "images", "limit": 5, "offset": 0, "column": "filename;drop", "equals": "x"},
        )
        assert rejected["error"]
        assert rejected["rows"] == []
    finally:
        handle.close()


def test_without_the_native_module_a_handle_stays_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("middleware.src.services.library.attach._database_importable", lambda: False)

    class _Handle:
        def query(self, *_args, **_kwargs):
            raise AssertionError("raw SQL must not run when the native module is absent")

        def execute(self, *_args, **_kwargs):
            raise AssertionError("raw SQL must not run when the native module is absent")

    server = SidecarServer(stdout=io.StringIO())
    attach_library(server, _Handle())
    assert server.library_store is None
    assert server.library_admin_store is None
    assert server.scan_service is None
    saved = handle_save_metadata(
        server.scan_service,
        {"items": [{"path": "/tmp/redo3-library/memory.png", "tags": ["art"], "group_name": "Studio"}]},
    )
    assert saved["success"] is False
    assert saved["saved_count"] == 0
    assert saved["database_available"] is False
