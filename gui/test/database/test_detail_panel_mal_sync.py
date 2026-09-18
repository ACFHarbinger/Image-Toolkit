"""MAL Auto-Fill error handling: the error dialog offers a direct Retry
action (not just dismiss-then-re-click-the-button-yourself)."""

from unittest.mock import patch

import pytest

from gui.src.elements.database.display.detail_panel import _DetailPanel

pytestmark = pytest.mark.gui


def _mal_sync_target(name: str) -> str:
    return f"gui.src.elements.database.display.detail_panel._mal_sync.{name}"


class TestMalFetchErrorRetry:
    def test_retry_button_re_triggers_fetch(self, q_app):
        panel = _DetailPanel()
        panel.f_title.setText("Some Title")

        with (
            patch(_mal_sync_target("QMessageBox")) as mock_box_cls,
            patch.object(panel, "_on_fetch_mal_clicked") as mock_refetch,
        ):
            mock_box = mock_box_cls.return_value
            retry_btn = object()
            mock_box.addButton.side_effect = [retry_btn, None]
            mock_box.clickedButton.return_value = retry_btn

            panel._on_mal_error(RuntimeError("boom"))

            mock_box.exec.assert_called_once()
            # First call to _on_mal_error's own re-enable path already ran
            # (btn_mal reset) before the dialog -- the retry click triggers
            # a SECOND, fresh fetch attempt.
            mock_refetch.assert_called_once()

    def test_close_button_does_not_re_trigger_fetch(self, q_app):
        panel = _DetailPanel()
        panel.f_title.setText("Some Title")

        with (
            patch(_mal_sync_target("QMessageBox")) as mock_box_cls,
            patch.object(panel, "_on_fetch_mal_clicked") as mock_refetch,
        ):
            mock_box = mock_box_cls.return_value
            retry_btn = object()
            close_btn = object()
            mock_box.addButton.side_effect = [retry_btn, close_btn]
            mock_box.clickedButton.return_value = close_btn

            panel._on_mal_error(RuntimeError("boom"))

            mock_refetch.assert_not_called()

    def test_error_re_enables_button_before_dialog_shown(self, q_app):
        panel = _DetailPanel()
        panel.btn_mal.setEnabled(False)
        panel.btn_mal.setText("Fetching...")

        with patch(_mal_sync_target("QMessageBox")):
            panel._on_mal_error(RuntimeError("boom"))

        assert panel.btn_mal.isEnabled()
        assert panel.btn_mal.text() == "Auto-Fill from MAL"

    def test_dialog_uses_critical_icon_and_exception_text(self, q_app):
        panel = _DetailPanel()

        with patch(_mal_sync_target("QMessageBox")) as mock_box_cls:
            mock_box = mock_box_cls.return_value
            panel._on_mal_error(RuntimeError("network is down"))

            mock_box.setIcon.assert_called_once_with(mock_box_cls.Icon.Critical)
            mock_box.setText.assert_called_once_with("network is down")
