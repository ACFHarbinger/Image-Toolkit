import platform

IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_DARWIN = platform.system() == "Darwin"

try:
    import base as base  # type: ignore

    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False
