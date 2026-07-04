"""Bridge configuration & pairing token (§7.5A).

Config lives in ``~/.image-toolkit/extension-bridge/config.json``::

    {
      "dup_root": "/mnt/images",   // directory tree searched by dup-check
      "recursive": true,
      "threshold": 10              // default Hamming threshold
    }

The pairing token is auto-generated on first use and stored next to it in
``token.txt``; the desktop app's settings UI displays it for the user to
paste into the extension options page.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Dict

from backend.src.core.dir_phash_index import BRIDGE_DIR, DEFAULT_THRESHOLD

logger = logging.getLogger(__name__)

CONFIG_PATH = BRIDGE_DIR / "config.json"
TOKEN_PATH = BRIDGE_DIR / "token.txt"

DEFAULT_CONFIG: Dict[str, Any] = {
    "dup_root": "",
    "recursive": True,
    "threshold": DEFAULT_THRESHOLD,
}


def load_config() -> Dict[str, Any]:
    """Read the bridge config, filling in defaults for missing keys."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        logger.warning("extension bridge config unreadable: %s", exc)
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)


def get_token() -> str:
    """Return the pairing token, generating and persisting one on first call."""
    try:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("extension bridge token unreadable: %s", exc)

    token = secrets.token_urlsafe(32)
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except OSError:
        pass
    logger.info("extension bridge token generated at %s", TOKEN_PATH)
    return token
