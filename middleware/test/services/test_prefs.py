"""prefs.describe never opens the vault (#917)."""

from __future__ import annotations

import ast
import io
from pathlib import Path
from typing import Any

import pytest
from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.prefs.describe import REASON, SECTIONS, describe
from middleware.src.sidecar.server import SidecarServer


def test_describe_lists_the_six_sections() -> None:
    result = describe("  ada  ")
    assert result == {
        "sections": list(SECTIONS),
        "credentials_changed": False,
        "reason": REASON,
    }
    assert result["sections"] == [
        "appearance",
        "profiles",
        "shortcuts",
        "tab_config",
        "credentials",
        "reset",
    ]
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


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str = "req-1") -> dict[str, Any]:
    frame = server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    assert isinstance(frame, dict)
    return frame


def test_sidecar_describe_rejects_blank_account_and_returns_locked_sections() -> None:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "prefs" in handshake["result"]["capabilities"]

    blank = _request(server, "prefs.describe", {"account": " "})
    assert blank["error"]["data"]["code"] == "bridge.invalid_params"

    described = _request(server, "prefs.describe", {"account": "ada"}, "req-2")
    assert described["result"]["credentials_changed"] is False
    assert described["result"]["reason"] == REASON
    assert described["result"]["sections"] == list(SECTIONS)
