import platform

IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_DARWIN = platform.system() == "Darwin"
# KDE desktop-containment-to-monitor detection, consumed by
# _KDEWallpaperMixin.get_kde_desktops(). True trusts each containment's own
# ``screen`` property (reported by Plasma via the scripting API). False uses
# get_kde_desktops_by_position() instead, which identifies each display by
# its screenGeometry() X/Y position -- for Plasma sessions where ``screen``
# is stuck at -1 for every containment (observed on Plasma 6.6.6 after a
# monitor hotplug/suspend, surviving a plasmashell restart).
USE_OS_DISPLAY_MAPPING = False
try:
    import base as base  # type: ignore
    if getattr(base, "__file__", None) is None:
        raise ImportError("base is a namespace package, not the compiled extension")
    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False
