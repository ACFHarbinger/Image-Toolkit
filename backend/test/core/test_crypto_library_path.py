"""Native crypto artifact discovery regressions."""

from pathlib import Path

from backend.src.constants import paths


def test_base_build_crypto_library_has_priority_over_legacy_build():
    root_library = paths.ROOT_DIR / paths._crypto_lib_name
    legacy_library = paths.ROOT_DIR / "build" / "crypto" / paths._crypto_lib_name

    if root_library.exists() and legacy_library.exists():
        assert Path(paths.CRYPTO_LIB_FILE) == root_library
