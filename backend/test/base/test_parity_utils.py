"""
backend/test/base/test_parity_utils.py
========================================
Phase 12 integration tests for base.utils (Phase 10) and base.web (Phase 9).

Tests are skipped when the C++ base extension is not built.

Run (when base is built):
    pytest backend/test/base/test_parity_utils.py -v
"""

from __future__ import annotations

import json

import pytest

try:
    import base as _base

    HAS_BASE = hasattr(_base, "utils") and hasattr(_base, "web")
except ImportError:
    HAS_BASE = False

pytestmark = pytest.mark.skipif(
    not HAS_BASE, reason="base C++ extension not built"
)

# ---------------------------------------------------------------------------
# base.utils.run_slideshow_daemon
# ---------------------------------------------------------------------------

class TestSlideshowDaemon:
    def test_status_returns_string(self):
        result = _base.utils.run_slideshow_daemon("status", {})
        assert isinstance(result, str)

    def test_status_is_valid_json(self):
        result = _base.utils.run_slideshow_daemon("status", {})
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_configure_returns_json_with_status_key(self):
        result = _base.utils.run_slideshow_daemon("configure", {"interval_seconds": 30})
        parsed = json.loads(result)
        assert "status" in parsed or "error" in parsed

    def test_start_with_empty_images_does_not_raise(self):
        try:
            result = _base.utils.run_slideshow_daemon("start", {"images": []})
            assert isinstance(result, str)
        except RuntimeError:
            pass  # acceptable — no images is an error condition

    def test_function_is_callable(self):
        assert callable(_base.utils.run_slideshow_daemon)

    def test_stop_returns_string(self):
        result = _base.utils.run_slideshow_daemon("stop", {})
        assert isinstance(result, str)

    def test_next_returns_string(self):
        result = _base.utils.run_slideshow_daemon("next", {})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# base.utils.run_legacy_migration
# ---------------------------------------------------------------------------

class TestLegacyMigration:
    def test_function_is_callable(self):
        assert callable(_base.utils.run_legacy_migration)

    def test_missing_sqlcipher_raises_runtime_error(self):
        # When compiled without SQLCipher, run_legacy_migration must raise RuntimeError.
        # When SQLCipher IS present this test is skipped via the xfail mechanism below.
        has_sqlcipher = getattr(_base.utils, "_has_sqlcipher", False)
        if has_sqlcipher:
            pytest.skip("SQLCipher available; stub-error test not applicable")
        with pytest.raises(RuntimeError, match="[Ss][Qq][Ll][Cc]ipher|not available|not compiled"):
            _base.utils.run_legacy_migration("user", "pass", "/tmp/vault.json", "/tmp/out.db")


# ---------------------------------------------------------------------------
# base.web stubs and callables
# ---------------------------------------------------------------------------

class TestWebCallables:
    def test_run_reverse_image_search_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            _base.web.run_reverse_image_search("https://example.com/img.jpg", {}, lambda s: None)

    def test_run_image_crawler_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            _base.web.run_image_crawler({}, lambda s: None)

    def test_run_board_crawler_is_callable(self):
        assert callable(_base.web.run_board_crawler)

    def test_run_sync_is_callable(self):
        assert callable(_base.web.run_sync)

    def test_board_crawler_bad_provider_raises(self):
        with pytest.raises((RuntimeError, ValueError, KeyError)):
            _base.web.run_board_crawler("__nonexistent__", {}, lambda s: None)
