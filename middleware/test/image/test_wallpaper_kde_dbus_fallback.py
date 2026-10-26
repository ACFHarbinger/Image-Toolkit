from unittest.mock import patch

import pytest
from src.core.wallpaper._dbus import evaluate_kde_script_with_fallback


class TestEvaluateKdeScriptWithFallback:
    """A ``base.evaluate_kde_script`` (qdbus CLI) failure must fall through
    to the dbus-python path, per this function's own docstring -- it
    previously re-raised immediately instead, silently skipping the
    fallback it claimed (in a log line) to be trying."""

    def test_qdbus_success_short_circuits_fallback(self):
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
            mock_base.evaluate_kde_script.return_value = "ok"
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python"
            ) as mock_fallback:
                result = evaluate_kde_script_with_fallback("qdbus6", "script")

        assert result == "ok"
        mock_fallback.assert_not_called()

    def test_qdbus_failure_falls_through_to_dbus_python(self):
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
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

    def test_broken_qdbus_does_not_block_when_qdbus6_works(self):
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
            def fake_eval(bin_name, script):
                if bin_name == "qdbus":
                    raise RuntimeError("qdbus: could not find a Qt installation of ''")
                if bin_name == "qdbus6":
                    return "ok-from-qdbus6"
                raise RuntimeError(f"unexpected bin {bin_name}")
            mock_base.evaluate_kde_script.side_effect = fake_eval
            with patch("src.core.wallpaper._dbus.shutil.which", side_effect=lambda x: f"/usr/bin/{x}"):
                result = evaluate_kde_script_with_fallback("qdbus", "script")
        assert result == "ok-from-qdbus6"

    def test_both_paths_failing_raises(self):
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
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
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
            mock_base.evaluate_kde_script.side_effect = AttributeError("stale base module")
            with patch(
                "src.core.wallpaper._dbus.evaluate_kde_script_dbus_python",
                side_effect=ImportError("no dbus-python"),
            ), pytest.raises(RuntimeError, match="qdbus6.*dbus-python"):
                evaluate_kde_script_with_fallback("qdbus6", "script")


class TestDesktopsFallback:
    """After a plasmashell restart ``currentActivity()`` can be empty, so
    ``desktops()`` returns nothing and every write failed with "monitor N
    has no valid KDE desktop/screen". Scripts now go through itkDesktops(),
    which falls back to desktopsForActivity()."""

    def test_desktops_calls_are_routed_through_the_fallback(self):
        from src.core.wallpaper._dbus import with_desktops_fallback

        out = with_desktops_fallback("var d = desktops()[1]; var n = desktops().length;")
        assert "function itkDesktops()" in out
        assert "desktopsForActivity(" in out
        assert out.endswith("var d = itkDesktops()[1]; var n = itkDesktops().length;")

    def test_scripts_without_desktops_are_unchanged(self):
        from src.core.wallpaper._dbus import with_desktops_fallback

        script = "print(screenCount); var x = obj.desktops();"
        assert with_desktops_fallback(script) == script

    def test_evaluate_sends_the_rewritten_script(self):
        with patch("src.core.wallpaper._dbus.backend") as mock_base:
            mock_base.evaluate_kde_script.return_value = ""
            evaluate_kde_script_with_fallback("qdbus6", "desktops()[0].reloadConfig();")
        sent = mock_base.evaluate_kde_script.call_args.args[1]
        assert sent.endswith("itkDesktops()[0].reloadConfig();")
