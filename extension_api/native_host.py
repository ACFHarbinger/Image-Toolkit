#!/usr/bin/env python3
"""§7.5B — Native messaging host for the browser-extension bridge.

Chrome/Firefox/Edge/Brave's Native Messaging API lets an extension launch
this script and exchange length-prefixed JSON messages over stdin/stdout,
bypassing the extension's HTTP-only sandbox entirely. This is the
"hardening, later" transport the roadmap describes as an alternative to
§7.5A's HTTP bridge: no open localhost port, no pairing-token UX — the
browser itself is the security boundary, since a native host can only ever
be launched by an extension ID explicitly listed in this host's installed
manifest (``allowed_origins`` on Chromium, ``allowed_extensions`` on
Firefox). See ``desktop/linux/scripts/install_native_host.sh`` for how the
manifests get installed.

Wire protocol (Chrome/Firefox native messaging spec): each message, both
directions, is a 4-byte **native-byte-order** unsigned length prefix
followed by that many bytes of UTF-8-encoded JSON. Request bodies:
``{"action": "ping"|"dup_check"|"ingest"|"similar"|"phash_snapshot", "payload": {...}}``
(``payload`` omitted/ignored for ``ping``/``phash_snapshot``). Responses:
``{"ok": bool, "status": int, "body": {...}}`` — ``status`` mirrors the
HTTP status code ``bridge_handlers`` would have returned for the same
request over §7.5A, so client code can share result-handling logic across
both transports (a 409 means "duplicate"/"not configured" either way, a
400 means bad input, etc.) even though there's no real HTTP status line
here.

This script deliberately does NOT depend on Django being set up
(``django.setup()``/``DJANGO_SETTINGS_MODULE``) — ``bridge_handlers`` and
everything it calls (``bridge_config``, ``DirPhashIndex``) are plain
Python/SQLite with no Django ORM dependency, so the host starts fast and
without a settings module, which matters since native messaging hosts are
launched fresh per connection by the browser.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import sys
from pathlib import Path

# Native messaging hosts are launched with an unpredictable cwd — make sure
# the repo root is importable regardless of how the launcher script invokes
# this file.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from extension_api import bridge_handlers  # noqa: E402

_LOG_PATH = Path.home() / ".image-toolkit" / "extension-bridge" / "native_host.log"


def _configure_logging() -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(_LOG_PATH),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        # Logging is best-effort; never let a filesystem issue crash the host.
        logging.basicConfig(level=logging.CRITICAL)


logger = logging.getLogger(__name__)


def read_message(stream) -> "dict | None":
    """Read one length-prefixed JSON message from ``stream``, or ``None`` at EOF."""
    raw_length = stream.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    (length,) = struct.unpack("@I", raw_length)
    data = stream.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


def write_message(stream, message: dict) -> None:
    """Write one length-prefixed JSON message to ``stream``."""
    encoded = json.dumps(message).encode("utf-8")
    stream.write(struct.pack("@I", len(encoded)))
    stream.write(encoded)
    stream.flush()


def dispatch(message: dict) -> dict:
    """Route one decoded request message to its handler, framing-agnostic."""
    action = message.get("action")
    handler = bridge_handlers.HANDLERS.get(action)
    if handler is None:
        return {
            "ok": False,
            "status": 400,
            "body": {"error": f"Unknown action: {action!r}"},
        }
    try:
        status, body = handler(message.get("payload") or {})
    except Exception as exc:  # noqa: BLE001 — must never crash the host process
        logger.exception("handler %s raised", action)
        return {"ok": False, "status": 500, "body": {"error": str(exc)}}
    return {"ok": status < 400, "status": status, "body": body}


def main() -> None:
    _configure_logging()
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    logger.info("native host started, pid=%d", os.getpid())
    while True:
        try:
            message = read_message(stdin)
        except (json.JSONDecodeError, struct.error) as exc:
            logger.warning("malformed message: %s", exc)
            write_message(stdout, {"ok": False, "status": 400, "body": {"error": "Malformed message."}})
            continue
        if message is None:
            logger.info("stdin closed, exiting")
            break
        write_message(stdout, dispatch(message))


if __name__ == "__main__":
    main()
