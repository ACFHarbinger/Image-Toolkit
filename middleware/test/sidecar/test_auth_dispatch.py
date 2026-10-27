"""auth.unlock keeps a fake C++ session on the sidecar (#1106)."""

from __future__ import annotations

import io
import json
import sys
import types
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.auth.session import VaultOpenError
from middleware.src.services.auth.status import LOCKED_REASON, OPEN_REASON
from middleware.src.sidecar.server import SidecarServer


class FakeSession:
    def __init__(self, account: str) -> None:
        self.account = account
        self.open = True
        self.locked = False

    def shutdown(self) -> None:
        self.open = False
        self.locked = True


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready(opener: Any | None = None) -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO(), vault_opener=opener)
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "auth" in handshake["result"]["capabilities"]
    return server


def test_status_returns_the_locked_session() -> None:
    server = _ready()
    response = _request(server, "auth.status", {"account": "  keeper  "}, "auth")
    assert response["result"] == {
        "unlocked": False,
        "account": "keeper",
        "reason": LOCKED_REASON,
    }


def test_blank_account_is_invalid_and_does_not_echo() -> None:
    server = _ready()
    secret = "not-a-password"
    response = _request(server, "auth.status", {"account": f"  {secret}  "}, "blank")
    assert response["result"]["account"] == secret
    blank = _request(server, "auth.status", {"account": "   "}, "blank-account")
    assert blank["error"]["data"]["code"] == "bridge.invalid_params"
    assert blank["error"]["data"]["details"]["reason"] == "ValueError"
    assert secret not in json.dumps(blank)
    missing = _request(server, "auth.status", {}, "missing")
    assert missing["error"]["data"]["code"] == "bridge.invalid_params"


def test_unlock_holds_the_fake_session_and_lock_drops_it() -> None:
    password = "s3cret-value"
    held: list[FakeSession] = []

    def opener(account: str, given: str) -> FakeSession:
        assert given == password
        session = FakeSession(account)
        held.append(session)
        return session

    server = _ready(opener)
    opened = _request(server, "auth.unlock", {"account": " keeper ", "password": password}, "open")
    assert opened["result"] == {
        "success": True,
        "account": "keeper",
        "message": "C++ vault session open.",
    }
    assert password not in json.dumps(opened)
    assert "vses_" not in json.dumps(opened)
    status = _request(server, "auth.status", {"account": "keeper"}, "status")
    assert status["result"] == {"unlocked": True, "account": "keeper", "reason": OPEN_REASON}
    locked = _request(server, "auth.lock", {"account": "keeper"}, "lock")
    assert locked["result"] == {"success": True, "account": "keeper"}
    assert held[0].locked is True
    assert server.auth.session is None
    after = _request(server, "auth.status", {"account": "keeper"}, "after")
    assert after["result"]["unlocked"] is False
    assert after["result"]["reason"] == LOCKED_REASON
    assert password not in json.dumps(locked) + json.dumps(after)


def test_unlock_forwards_the_opened_session_and_lock_forwards_none() -> None:
    calls: list[Any] = []
    module = types.ModuleType("middleware.src.services.library.lifecycle")

    def bind_vault_session(session: Any) -> None:
        calls.append(session)

    module.bind_vault_session = bind_vault_session
    previous = sys.modules.get(module.__name__)
    sys.modules[module.__name__] = module
    try:
        password = "s3cret-value"

        def opener(account: str, given: str) -> FakeSession:
            assert given == password
            return FakeSession(account)

        server = _ready(opener)
        opened = _request(server, "auth.unlock", {"account": " keeper ", "password": password}, "open")
        assert opened["result"]["success"] is True
        assert calls == [server.auth.session]
        assert calls[0].account == "keeper"
        held = calls[0]
        wrong = _request(server, "auth.lock", {"account": "other"}, "wrong")
        assert wrong["result"]["success"] is False
        assert calls == [held]
        locked = _request(server, "auth.lock", {"account": "keeper"}, "lock")
        assert locked["result"]["success"] is True
        assert calls == [held, None]
        assert password not in json.dumps(opened) + json.dumps(locked)

        rejected: list[Any] = []

        def bind_rejected(session: Any) -> None:
            rejected.append(session)

        module.bind_vault_session = bind_rejected

        def reject(_account: str, _given: str) -> FakeSession:
            raise VaultOpenError("Invalid password.")

        refused = _ready(reject)
        failed = _request(refused, "auth.unlock", {"account": "keeper", "password": password}, "reject")
        assert failed["result"]["success"] is False
        assert rejected == []
        assert refused.auth.session is None
    finally:
        if previous is None:
            sys.modules.pop(module.__name__, None)
        else:
            sys.modules[module.__name__] = previous


def test_rejected_unlock_does_not_pretend_the_session_is_open() -> None:
    password = "s3cret-value"

    def opener(_account: str, _given: str) -> FakeSession:
        raise VaultOpenError("Invalid password.")

    server = _ready(opener)
    opened = _request(server, "auth.unlock", {"account": "keeper", "password": password}, "open")
    assert opened["result"]["success"] is False
    assert opened["result"]["message"] == "Invalid password."
    assert password not in json.dumps(opened)
    status = _request(server, "auth.status", {"account": "keeper"}, "status")
    assert status["result"]["unlocked"] is False
    assert server.auth.session is None


def test_missing_native_module_returns_success_false() -> None:
    password = "s3cret-value"

    def missing(_account: str, _given: str) -> None:
        raise VaultOpenError("C++ vault module is missing.")

    server = _ready(missing)
    opened = _request(server, "auth.unlock", {"account": "keeper", "password": password}, "open")
    assert opened["result"]["success"] is False
    assert "missing" in opened["result"]["message"]
    assert password not in json.dumps(opened)
    status = _request(server, "auth.status", {"account": "keeper"}, "status")
    assert status["result"]["unlocked"] is False
