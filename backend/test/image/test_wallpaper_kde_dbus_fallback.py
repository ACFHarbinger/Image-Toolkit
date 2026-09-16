from unittest.mock import patch

import pytest
from src.core.wallpaper._dbus import evaluate_kde_script_with_fallback


class TestEvaluateKdeScriptWithFallback:
    """A ``base.evaluate_kde_script`` (qdbus CLI) failure must fall through
    to the dbus-python path, per this function's own docstring -- it
    previously re-raised immediately instead, silently skipping the
    fallback it claimed (in a log line) to be trying."""

    def test_qdbus_success_short_circuits_fallback(self):
        with patch("src.core.wallpaper._dbus.base") as mock_base:
            mock_base.evaluate_kde_script.return_value = "ok"
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python"
            ) as mock_fallback:
                result = evaluate_kde_script_with_fallback("qdbus6", "script")

        assert result == "ok"
        mock_fallback.assert_not_called()

    def test_qdbus_failure_falls_through_to_dbus_python(self):
        with patch("src.core.wallpaper._dbus.base") as mock_base:
            mock_base.evaluate_kde_script.side_effect = AttributeError(
                "module 'base' has no attribute 'evaluate_kde_script'"
            )
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python",
                return_value="fallback-ok",
            ) as mock_fallback:
                result = evaluate_kde_script_with_fallback("qdbus6", "script")

        assert result == "fallback-ok"
        mock_fallback.assert_called_once_with("script")

    def test_both_paths_failing_raises(self):
        with patch("src.core.wallpaper._dbus.base") as mock_base:
            mock_base.evaluate_kde_script.side_effect = RuntimeError("qdbus boom")
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python",
                side_effect=RuntimeError("dbus-python boom"),
            ), pytest.raises(RuntimeError, match="dbus-python boom"):
                evaluate_kde_script_with_fallback("qdbus6", "script")

    def test_no_qdbus_goes_straight_to_dbus_python(self):
        with patch(
            "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python",
            return_value="fallback-ok",
        ) as mock_fallback:
            result = evaluate_kde_script_with_fallback(None, "script")

        assert result == "fallback-ok"
        mock_fallback.assert_called_once_with("script")

    def test_dbus_python_import_error_raises_actionable_runtime_error(self):
        with patch("src.core.wallpaper._dbus.base") as mock_base:
            mock_base.evaluate_kde_script.side_effect = AttributeError("stale base module")
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python",
                side_effect=ImportError("no dbus-python"),
            ), pytest.raises(RuntimeError, match="qdbus6.*dbus-python"):
                evaluate_kde_script_with_fallback("qdbus6", "script")
