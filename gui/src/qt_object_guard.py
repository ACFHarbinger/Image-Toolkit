"""Shared guard for wrapped-C++-object teardown races (R0.6, #552).

Teardown paths routinely touch widgets that are already deleted on the C++
side (tab closed, window disposed). The expected shapes are PySide6's
``RuntimeError`` ("Internal C++ object ... already deleted."), PyQt's
"wrapped C/C++ object ..." variant, and ``ReferenceError`` from dead
weakrefs: debug-logged and swallowed. Anything else is a real bug and is
re-raised instead of being silenced.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_DELETED_MARKERS = (
    "already deleted",
    "wrapped c/c++ object",
    "internal c++ object",
    "has been deleted",
)


def is_deleted_qobject_error(exc: BaseException) -> bool:
    """True for the known already-deleted Qt object shapes."""
    if isinstance(exc, ReferenceError):
        return True
    return isinstance(exc, RuntimeError) and any(
        marker in str(exc).lower() for marker in _DELETED_MARKERS
    )


def deleted_qobject_guard(exc: BaseException, context: str = "") -> None:
    """Swallow an expected teardown race, re-raise anything else.

    Call as ``except RuntimeError as exc: deleted_qobject_guard(exc, "<what>")``.
    """
    if is_deleted_qobject_error(exc):
        logger.debug("Ignoring teardown race in %s: %r", context or "GUI teardown", exc)
        return
    raise exc
