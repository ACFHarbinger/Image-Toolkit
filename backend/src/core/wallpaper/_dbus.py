"""KDE per-monitor wallpaper via D-Bus (§4.7).

``qdbus`` binary names vary by Linux distro:
  Ubuntu/Debian: qdbus-qt6  (Qt6 KDE)  or  qdbus  (may be Qt5)
  Arch/Manjaro:  qdbus  (always Qt6 on current Plasma 6)
  OpenSUSE/Fedora: qdbus6
We try all known names in descending preference order.
"""

import logging
import shutil
from typing import Optional

import base  # Native extension

from backend.src.constants.core import _QDBUS_CANDIDATES

logger = logging.getLogger(__name__)


def find_qdbus_binary() -> Optional[str]:
    """Return the first available ``qdbus`` binary name, or ``None``.

    Tries ``qdbus6``, ``qdbus-qt6``, ``qdbus``, ``qdbus-qt5`` in that order.
    The result is not cached — call once at startup and store the value.
    """
    for name in _QDBUS_CANDIDATES:
        if shutil.which(name):
            return name
    return None


def evaluate_kde_script_dbus_python(script: str) -> str:
    """Call ``org.kde.PlasmaShell.evaluateScript`` via ``dbus-python``.

    Pure-Python fallback for environments where the ``qdbus``/``qdbus6`` CLI
    binary is unavailable.  Requires the ``dbus-python`` package (``pip install
    dbus-python``).  Raises ``ImportError`` if ``dbus`` is not installed and
    ``RuntimeError`` if the D-Bus call fails.

    Parameters
    ----------
    script : Plasma scripting JS to execute.

    Returns
    -------
    str — stdout captured from the D-Bus call.
    """
    import dbus  # type: ignore[import-untyped]

    bus = dbus.SessionBus()
    plasma_obj = bus.get_object("org.kde.plasmashell", "/PlasmaShell")
    iface = dbus.Interface(plasma_obj, dbus_interface="org.kde.PlasmaShell")
    result = iface.evaluateScript(script)
    return str(result) if result is not None else ""


def evaluate_kde_script_with_fallback(qdbus: Optional[str], script: str) -> str:
    """Evaluate a Plasma JS script via qdbus CLI, falling back to dbus-python.

    Chain:
    1. If *qdbus* is a non-empty string: call ``base.evaluate_kde_script(qdbus, script)``.
    2. If that fails (or qdbus is None): try ``evaluate_kde_script_dbus_python()``.
    3. If both fail: re-raise the most recent exception.

    Returns the script output string.
    """
    if qdbus:
        try:
            return base.evaluate_kde_script(qdbus, script)
        except Exception as exc:
            logger.debug("qdbus CLI failed (%s), trying dbus-python fallback.", exc)
            raise exc from None
    try:
        return evaluate_kde_script_dbus_python(script)
    except ImportError:
        raise RuntimeError(
            "Neither qdbus CLI nor dbus-python is available. "
            "Install 'qdbus6'/'qdbus-qt6' or 'dbus-python' to enable KDE wallpaper support."
        ) from None
    except Exception as exc:
        raise exc from None


__all__ = [
    "find_qdbus_binary",
    "evaluate_kde_script_dbus_python",
    "evaluate_kde_script_with_fallback",
]
