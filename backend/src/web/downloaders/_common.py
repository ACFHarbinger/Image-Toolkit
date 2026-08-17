"""Shared helpers for web media downloaders.

Both the Reddit and nhentai downloaders hit the same two problems that
made downloads unreliable:

1. **No retry on transient failures.** A single GET with no retry meant a
   429 / 5xx / momentary network blip silently skipped that file (the
   downloaders treat a failed file as non-fatal and continue), so the first
   run of a URL would reliably miss a few images and the user had to click
   Download again to pick them up. This module centralises a small retry
   loop with backoff for exactly those transient statuses/errors.

2. **No existing-file policy.** Every file was written with open(dest, "wb")
   which always overwrites, so re-running the same URL had no way to skip
   or to keep both copies. This module centralises the skip / overwrite /
   rename-with-counter decision.

Both downloaders use these helpers so the two policies stay identical.
"""

from __future__ import annotations

import os
import time
from typing import Optional

# Number of attempts per file (1 initial + retries).
MAX_ATTEMPTS = 3
# Base backoff seconds; each retry doubles it (0.5, 1.0).
BACKOFF_BASE_SECONDS = 0.5

# HTTP statuses worth retrying: rate limiting and transient server errors.
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# on_exists policy values shared with the GUI dropdown.
ON_EXISTS_OVERWRITE = "overwrite"
ON_EXISTS_SKIP = "skip"
ON_EXISTS_RENAME = "rename"
ON_EXISTS_DEFAULT = ON_EXISTS_OVERWRITE


def is_retryable_status(status_code: int) -> bool:
    """Whether an HTTP status should be retried rather than treated as fatal."""
    return status_code in _RETRYABLE_STATUSES


def backoff_sleep(attempt: int) -> None:
    """Sleep between attempts: 0.5s then 1.0s for the default MAX_ATTEMPTS."""
    time.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))


def resolve_dest_path(dest: str, on_exists: str) -> Optional[str]:
    """Return the file path to write for a download, honouring on_exists.

    - "overwrite": return dest unchanged (write over it).
    - "skip": return None if dest already exists (caller skips the file).
    - "rename": if dest exists, find the next free name(N).ext where N
      counts existing files with that same stem (1, 2, ...).

    For rename, name.jpg colliding with an existing file becomes
    name(1).jpg; if that also exists, name(2).jpg, and so on. This is the
    <FILENAME>(<FILE_NUMBER>).<FILE_EXTENSION> format from the feature
    request.
    """
    if not os.path.exists(dest):
        return dest
    if on_exists == ON_EXISTS_SKIP:
        return None
    if on_exists == ON_EXISTS_RENAME:
        stem, ext = os.path.splitext(dest)
        number = 1
        while True:
            candidate = f"{stem}({number}){ext}"
            if not os.path.exists(candidate):
                return candidate
            number += 1
    return dest  # overwrite


__all__ = [
    "MAX_ATTEMPTS",
    "BACKOFF_BASE_SECONDS",
    "ON_EXISTS_OVERWRITE",
    "ON_EXISTS_SKIP",
    "ON_EXISTS_RENAME",
    "ON_EXISTS_DEFAULT",
    "is_retryable_status",
    "backoff_sleep",
    "resolve_dest_path",
]
