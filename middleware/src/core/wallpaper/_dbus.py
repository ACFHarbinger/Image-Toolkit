"""KDE per-monitor wallpaper via D-Bus (§4.7).

``qdbus`` binary names vary by Linux distro:
  Ubuntu/Debian: qdbus-qt6  (Qt6 KDE)  or  qdbus  (may be Qt5)
  Arch/Manjaro:  qdbus  (always Qt6 on current Plasma 6)
  OpenSUSE/Fedora: qdbus6
We try all known names in descending preference order.
"""

import logging
import re
import shutil
import subprocess
from typing import Optional

import backend  # Native extension

from middleware.src.constants.core import _QDBUS_CANDIDATES

logger = logging.getLogger(__name__)


# After a plasmashell restart, Plasma's scripting ``currentActivity()`` can
# come back empty, and ``desktops()`` -- which only lists the current
# activity's containments -- then returns nothing even though the desktop
# containments still exist (``desktopsForActivity()`` lists them). Every
# script's ``desktops()`` call is routed through this fallback: the current
# activity first, then the activity with one desktop per screen. Containments
# are ordered by screen, or by id when ``screen`` reads -1 (the same
# desktop-index <-> output-index correspondence ``desktops()`` gives).
_DESKTOPS_FALLBACK_JS = """
function itkDesktops() {
    var ds = desktops();
    if (ds.length) return ds;
    var acts = [];
    try { var cur = currentActivity(); if (cur) acts.push(cur); } catch (e) {}
    try {
        var all = activities();
        for (var k = 0; k < all.length; k++) if (acts.indexOf(all[k]) < 0) acts.push(all[k]);
    } catch (e) {}
    var found = [];
    for (var a = 0; a < acts.length; a++) {
        var da = [];
        try { da = desktopsForActivity(acts[a]); } catch (e) {}
        if (da.length === screenCount) { found = da; break; }
        if (!found.length && da.length) found = da;
    }
    var out = [];
    for (var j = 0; j < found.length; j++) out.push(found[j]);
    var byScreen = out.every(function (c) { return c.screen >= 0; });
    out.sort(function (x, y) { return byScreen ? x.screen - y.screen : x.id - y.id; });
    return out;
}
"""
_DESKTOPS_CALL = re.compile(r"(?<![\w.])desktops\(\)")


def with_desktops_fallback(script: str) -> str:
    """Route ``desktops()`` calls in *script* through ``itkDesktops()``."""
    if not _DESKTOPS_CALL.search(script):
        return script
    return _DESKTOPS_FALLBACK_JS + _DESKTOPS_CALL.sub("itkDesktops()", script)


def find_qdbus_binary() -> Optional[str]:
    """Return the first available working ``qdbus`` binary name, or ``None``.

    Tries ``qdbus6``, ``qdbus-qt6``, ``qdbus``, ``qdbus-qt5`` in that order.
    Skips any candidate whose invocation reports 'could not find a Qt installation'.
    """
    for name in _QDBUS_CANDIDATES:
        path = shutil.which(name)
        if not path:
            continue
        try:
            res = subprocess.run([path], capture_output=True, text=True, timeout=1.5)
            combined = (res.stdout + " " + res.stderr).lower()
            if "could not find a qt installation" in combined:
                logger.warning("Candidate %s failed Qt installation check; skipping", name)
                continue
            return name
        except Exception:
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
    """Evaluate a Plasma JS script via qdbus CLI, falling back across candidates and dbus-python.

    Chain:
    1. If *qdbus* is a non-empty string, try calling ``base.evaluate_kde_script(qdbus, script)``.
    2. If that fails (or qdbus is None), try all available candidates in ``_QDBUS_CANDIDATES``.
    3. If all candidates fail: try ``evaluate_kde_script_dbus_python()``.
    4. If both fail: re-raise the most recent exception.

    Returns the script output string.
    """
    script = with_desktops_fallback(script)
    candidates: list[str] = []
    if qdbus:
        candidates.append(qdbus)
    for c in _QDBUS_CANDIDATES:
        if c not in candidates and shutil.which(c):
            candidates.append(c)

    last_exc: Optional[Exception] = None
    for cand in candidates:
        try:
            return backend.evaluate_kde_script(cand, script)
        except Exception as exc:
            logger.debug("qdbus CLI candidate '%s' failed (%s)", cand, exc)
            last_exc = exc

    try:
        return evaluate_kde_script_dbus_python(script)
    except ImportError:
        if last_exc:
            raise RuntimeError(
                f"KDE scripting failed across candidates ({candidates}) and dbus-python is unavailable: {last_exc}"
            ) from last_exc
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
    "with_desktops_fallback",
]
