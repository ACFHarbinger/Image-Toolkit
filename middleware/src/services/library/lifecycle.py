"""Forward vault unlock and lock to every live sidecar.

``SidecarServer`` registers itself. Unlock passes the opened session; lock
passes ``None``. This module does not open the library database.
"""

from __future__ import annotations

import weakref
from typing import Any

_servers: weakref.WeakSet[Any] = weakref.WeakSet()


def register_server(server: Any) -> None:
    """Keep a live sidecar until it is no longer referenced elsewhere."""
    _servers.add(server)


def bind_vault_session(session: Any | None) -> None:
    """Attach ``session`` on every live sidecar. ``None`` clears the library."""
    for server in list(_servers):
        if session is None:
            server.clear_vault_session()
        else:
            server.bind_vault_session(session)


__all__ = ["bind_vault_session", "register_server"]
