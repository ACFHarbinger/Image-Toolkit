import platform

IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_DARWIN = platform.system() == "Darwin"

try:
    import base as base  # type: ignore
    if getattr(base, "__file__", None) is None:
        raise ImportError("base is a namespace package, not the compiled extension")
    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False
