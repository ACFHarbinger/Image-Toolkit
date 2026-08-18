"""Tests for Theme Studio panel (#438) and theme tools (#441)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gui.src.theming.schema import ThemePack

pytestmark = pytest.mark.gui


def _pack(**kw) -> ThemePack:
    base = ThemePack(name="test", **kw)
    return base


class TestThemeStudioPanel:
    def test_panel_builds_and_holds_pack(self, q_app):
        from gui.src.theming.theme_studio import ThemeStudioPanel

        pack = _pack()
        applied = []
        panel = ThemeStudioPanel(pack, apply_callback=applied.append)
        assert panel.pack is pack
        assert len(panel._swatches) == 5

    def test_edit_triggers_transactional_apply(self, q_app):
        from gui.src.theming.theme_studio import ThemeStudioPanel

        pack = _pack()
        applied = []
        panel = ThemeStudioPanel(pack, apply_callback=applied.append)
        # Change density -> candidate pack should be applied.
        panel.density_combo.setCurrentText("compact")
        assert applied, "edit should have applied a candidate pack"
        assert applied[-1].density.mode == "compact"

    def test_invalid_edit_rolls_back_to_valid_snapshot(self, q_app, monkeypatch):
        from gui.src.theming.schema import ThemeSchemaError
        from gui.src.theming.theme_studio import ThemeStudioPanel

        pack = _pack()
        applied = []
        panel = ThemeStudioPanel(pack, apply_callback=applied.append)
        before = panel.pack
        # Make the next candidate build raise (schema error) -> rollback
        # to the last valid snapshot, never leave the UI mid-broken.
        def _boom(self):
            raise ThemeSchemaError("forced invalid candidate")

        monkeypatch.setattr(ThemeStudioPanel, "_build_candidate", _boom)
        panel._on_edit()
        assert panel.pack == before
        assert "Reverted" in panel.contrast_label.text()

    def test_contrast_meter_reports_warnings(self, q_app):
        from gui.src.theming.theme_studio import ThemeStudioPanel

        # Low-contrast pack: dark text on dark bg.
        pack = ThemePack(
            name="low",
            color_overrides={"text": "#111111", "window_bg": "#222222"},
        )
        panel = ThemeStudioPanel(pack, apply_callback=lambda p: None)
        assert "WCAG" in panel.contrast_label.text()

    def test_color_pick_updates_swatch_and_candidate(self, q_app, monkeypatch):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        from gui.src.theming.theme_studio import ThemeStudioPanel

        pack = _pack()
        applied = []
        panel = ThemeStudioPanel(pack, apply_callback=applied.append)
        monkeypatch.setattr(
            QColorDialog, "getColor", lambda *a, **k: QColor("#ff00aa")
        )
        panel._pick_color("accent")
        assert panel._swatches["accent"].text() == "#ff00aa"
        assert applied[-1].color_overrides.get("accent") == "#ff00aa"


class TestQssEditorWidget:
    def test_editor_readonly_until_unrestricted(self, q_app, tmp_path):
        from gui.src.theming.theme_tools import QssEditorWidget

        qss = tmp_path / "user_theme.qss"
        qss.write_text("QPushButton { color: red; }")
        editor = QssEditorWidget(qss_path=qss)
        assert editor.editor.isReadOnly() is True
        assert editor.apply_button.isEnabled() is False
        editor.unrestricted_check.setChecked(True)
        assert editor.editor.isReadOnly() is False
        assert editor.apply_button.isEnabled() is True

    def test_save_and_apply_writes_file(self, q_app, tmp_path):
        from gui.src.theming.theme_tools import QssEditorWidget

        qss = tmp_path / "user_theme.qss"
        editor = QssEditorWidget(qss_path=qss)
        editor.unrestricted_check.setChecked(True)
        editor.editor.setPlainText("QPushButton { background: #123456; }")
        assert editor.save_and_apply() is True
        assert qss.read_text() == "QPushButton { background: #123456; }"

    def test_reset_removes_file(self, q_app, tmp_path):
        from gui.src.theming.theme_tools import QssEditorWidget

        qss = tmp_path / "user_theme.qss"
        qss.write_text("QPushButton { color: red; }")
        editor = QssEditorWidget(qss_path=qss)
        editor.reset_to_default()
        assert not qss.exists()


class TestThemeExportImport:
    def test_export_import_roundtrip(self, tmp_path):
        from gui.src.theming.theme_tools import export_theme_pack, import_theme_pack

        pack = ThemePack(
            name="roundtrip",
            color_overrides={"accent": "#ff00aa"},
            raw_qss="QPushButton { color: red; }",
        )
        dest = tmp_path / "theme.json"
        export_theme_pack(pack, dest)
        loaded = import_theme_pack(dest)
        assert loaded.name == "roundtrip"
        assert loaded.color_overrides == {"accent": "#ff00aa"}
        assert loaded.raw_qss == "QPushButton { color: red; }"

    def test_export_includes_asset_manifest(self, tmp_path):
        import json

        from gui.src.theming.schema import BackgroundAssetRef, BackgroundTokens
        from gui.src.theming.theme_tools import export_theme_pack

        pack = ThemePack(
            name="assets",
            backgrounds=(
                BackgroundTokens(
                    images=(BackgroundAssetRef(kind="imported", asset_id="abc123.png"),)
                ),
            ),
        )
        dest = tmp_path / "theme.json"
        export_theme_pack(pack, dest)
        data = json.loads(dest.read_text())
        assert data["asset_manifest"] == ["abc123.png"]

    def test_import_rejects_non_schema_doc(self, tmp_path):
        from gui.src.theming.schema import ThemeSchemaError
        from gui.src.theming.theme_tools import import_theme_pack

        bad = tmp_path / "bad.json"
        bad.write_text('{"schema": "not-a-theme", "name": "x"}')
        with pytest.raises(ThemeSchemaError):
            import_theme_pack(bad)
