"""Settings window store (#1112) and the vault-free section list (#917)."""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path
from typing import Any

import pytest
from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.bridge.envelope import BridgeAppError
from middleware.src.services.auth.status import auth_status
from middleware.src.services.prefs.describe import REASON, SECTIONS, describe
from middleware.src.services.prefs.password import LOCKED, set_master_password
from middleware.src.services.prefs.store import load_window, save_window
from middleware.src.sidecar.handlers.prefs import bind_prefs_paths, bind_vault_session
from middleware.src.sidecar.server import SidecarServer

_PROFILES = {"startup_category": "System Tools", "startup_tab": ""}
_GALLERY = {"thumbnail_size": 180, "page_size": 100, "confirm_deletions": True, "recursive_scan": True}
_LOGGING = {"level": "INFO", "file_logging": False}


def test_describe_lists_the_window_sections() -> None:
    result = describe("  ada  ")
    assert result == {
        "sections": list(SECTIONS),
        "credentials_changed": False,
        "reason": REASON,
    }
    assert result["sections"] == ["account", "profiles", "gallery", "logging", "shortcuts"]
    assert len(result["sections"]) == len(set(result["sections"]))


@pytest.mark.parametrize("account", ["", "   ", "\n\t"])
def test_empty_account_is_an_error(account: str) -> None:
    with pytest.raises(ValueError, match="account is required"):
        describe(account)


def test_describe_source_does_not_open_a_store() -> None:
    source = Path(describe.__code__.co_filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_from = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert imported_from == ["__future__", "typing"]
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    for forbidden in ("VaultManager", "sqlite", "library.db", "open("):
        assert forbidden not in source


def test_prefs_modules_do_not_import_gui_or_open_logs() -> None:
    root = Path(describe.__code__.co_filename).parent
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import gui" not in source
        assert "from gui" not in source
        assert "PySide6" not in source
        assert "subprocess" not in source
        assert "auth.status" not in source or path.name == "password.py"
    password = (root / "password.py").read_text(encoding="utf-8")
    assert "auth_status" not in password
    store = (root / "store.py").read_text(encoding="utf-8")
    assert "VaultManager" not in store
    assert ' / "logs"' not in store


def test_store_round_trip_stays_in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    prefs = tmp_path / "settings" / "window.json"
    keys = tmp_path / "keybindings.json"
    before = auth_status("ada")

    loaded = load_window("  ada  ", path=prefs, keybindings=keys)
    assert loaded["account"] == "ada"
    assert loaded["profiles"] == _PROFILES
    assert loaded["gallery"] == _GALLERY
    assert loaded["logging"] == _LOGGING
    assert any(row["id"] == "gallery.select_all" for row in loaded["shortcuts"])
    assert not prefs.exists()

    saved = save_window(
        "ada",
        {"startup_category": "Manga", "startup_tab": "Merge"},
        {"thumbnail_size": 200, "page_size": 150, "confirm_deletions": False, "recursive_scan": False},
        {"level": "WARNING", "file_logging": True},
        shortcut={"action": "gallery.select_all", "chord": "Meta+A"},
        path=prefs,
        keybindings=keys,
    )
    assert saved["profiles"] == {"startup_category": "Manga", "startup_tab": "Merge"}
    assert saved["gallery"]["thumbnail_size"] == 200
    assert saved["gallery"]["page_size"] == 150
    assert saved["gallery"]["confirm_deletions"] is False
    assert saved["logging"] == {"level": "WARNING", "file_logging": True}
    select_all = next(row for row in saved["shortcuts"] if row["id"] == "gallery.select_all")
    assert select_all["custom"] == "Meta+A"

    again = load_window("ada", path=prefs, keybindings=keys)
    assert again["profiles"] == saved["profiles"]
    assert again["gallery"] == saved["gallery"]
    assert again["logging"] == saved["logging"]
    assert next(row for row in again["shortcuts"] if row["id"] == "gallery.select_all")["custom"] == "Meta+A"
    assert json.loads(keys.read_text(encoding="utf-8"))["gallery.select_all"] == {
        "default_enabled": False,
        "custom": ["Meta+A"],
    }
    assert auth_status("ada") == before
    assert not (home / ".image-toolkit").exists()
    assert not (home / ".config").exists()


def test_unknown_shortcut_action_is_an_error(tmp_path: Path) -> None:
    prefs = tmp_path / "window.json"
    with pytest.raises(BridgeAppError, match="prefs.unknown_action"):
        save_window(
            "ada",
            _PROFILES,
            _GALLERY,
            _LOGGING,
            shortcut={"action": "not.a.real.action", "chord": "Ctrl+X"},
            path=prefs,
            keybindings=tmp_path / "keybindings.json",
        )
    assert not prefs.exists()


def test_password_change_requires_current_password_and_session(tmp_path: Path) -> None:
    prefs = tmp_path / "window.json"
    keys = tmp_path / "keybindings.json"
    before = auth_status("ada")

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            self.calls.append((account_name, new_raw_pass))

    refused = save_window(
        "ada",
        _PROFILES,
        _GALLERY,
        _LOGGING,
        current_password="old-secret",
        new_password="new-secret",
        path=prefs,
        keybindings=keys,
        session=None,
    )
    assert refused["success"] is False
    assert refused["credentials_changed"] is False
    assert refused["reason"] == LOCKED
    assert "new-secret" not in prefs.read_text(encoding="utf-8")
    assert "old-secret" not in prefs.read_text(encoding="utf-8")

    missing_current = set_master_password("ada", "   ", "new-secret", Session())
    assert missing_current["success"] is False
    assert missing_current["reason"] == LOCKED

    session = Session()
    changed = set_master_password("ada", "old-secret", "new-secret", session)
    assert changed == {"success": True, "credentials_changed": True, "reason": ""}
    assert session.calls == [("ada", "new-secret")]
    assert auth_status("ada") == before


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str = "req-1") -> dict[str, Any]:
    frame = server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    assert isinstance(frame, dict)
    return frame


@pytest.fixture
def bound_paths(tmp_path: Path):
    prefs = tmp_path / "window.json"
    keys = tmp_path / "keybindings.json"
    bind_prefs_paths(prefs=prefs, keybindings=keys)
    bind_vault_session(None)
    yield prefs, keys
    bind_prefs_paths(prefs=None, keybindings=None)
    bind_vault_session(None)


def _handshake(server: SidecarServer) -> dict[str, Any]:
    return _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )


def _set_params(**extra: Any) -> dict[str, Any]:
    params = {
        "account": "ada",
        "profiles": {"startup_category": "Library Database", "startup_tab": "Scan"},
        "gallery": {"thumbnail_size": 96, "page_size": 50, "confirm_deletions": True, "recursive_scan": False},
        "logging": {"level": "DEBUG", "file_logging": True},
    }
    params.update(extra)
    return params


def test_sidecar_describe_rejects_blank_account_and_returns_sections(bound_paths: tuple[Path, Path]) -> None:
    del bound_paths
    server = SidecarServer(stdout=io.StringIO())
    handshake = _handshake(server)
    assert "prefs" in handshake["result"]["capabilities"]
    assert "settings" in handshake["result"]["capabilities"]

    blank = _request(server, "prefs.describe", {"account": " "})
    assert blank["error"]["data"]["code"] == "bridge.invalid_params"

    described = _request(server, "prefs.describe", {"account": "ada"}, "req-2")
    assert described["result"]["credentials_changed"] is False
    assert described["result"]["reason"] == REASON
    assert described["result"]["sections"] == list(SECTIONS)


def test_sidecar_round_trip_password_and_unknown_action(bound_paths: tuple[Path, Path]) -> None:
    prefs, keys = bound_paths
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)

    got = _request(server, "prefs.get", {"account": "ada"}, "get")
    assert got["result"]["gallery"]["thumbnail_size"] == 180
    assert got["result"]["logging"]["level"] == "INFO"

    unknown = _request(server, "prefs.set", _set_params(shortcut={"action": "missing.action", "chord": "Ctrl+X"}), "bad")
    assert unknown["error"]["data"]["code"] == "prefs.unknown_action"
    assert not prefs.exists()

    locked = _request(
        server,
        "prefs.set",
        _set_params(current_password="old-secret", new_password="new-secret"),
        "set",
    )
    assert locked["result"]["success"] is False
    assert locked["result"]["reason"] == LOCKED
    assert locked["result"]["credentials_changed"] is False
    assert locked["result"]["profiles"]["startup_tab"] == "Scan"
    assert locked["result"]["logging"]["file_logging"] is True
    reloaded = _request(server, "prefs.get", {"account": "ada"}, "reload")
    assert reloaded["result"]["gallery"]["page_size"] == 50
    assert reloaded["result"]["profiles"]["startup_category"] == "Library Database"
    body = prefs.read_text(encoding="utf-8")
    assert "new-secret" not in body
    assert "old-secret" not in body
    assert not keys.exists()

    class Session:
        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            self.account_name = account_name
            self.new_raw_pass = new_raw_pass

    session = Session()
    bind_vault_session(session)
    changed = _request(
        server,
        "prefs.set",
        _set_params(
            current_password="old-secret",
            new_password="new-secret",
            shortcut={"action": "gallery.select_all", "chord": "Meta+A"},
        ),
        "changed",
    )
    assert changed["result"]["success"] is True
    assert changed["result"]["credentials_changed"] is True
    assert session.account_name == "ada"
    assert session.new_raw_pass == "new-secret"
    assert json.loads(keys.read_text(encoding="utf-8"))["gallery.select_all"]["custom"] == ["Meta+A"]
    assert "new-secret" not in prefs.read_text(encoding="utf-8")
