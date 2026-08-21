"""In-app QSS live editor + cross-surface theme export/import (#441).

Two deliverables from the locked roadmap:

1. **QssEditorWidget** -- an Advanced/expert subtab (behind an explicit
   unrestricted-mode toggle; safe styling is the default) that edits
   ~/.image-toolkit/user_theme.qss with live-reload preview and a
   one-click Reset to Default. Extends the existing load_user_qss_override
   hook rather than replacing it: the editor writes the same file that
   hook already reads at theme-apply time.

2. **Export/import** -- package a #437 ThemePack (JSON token pack +
   asset_ref background references) into a portable file, and load one
   back. The format is schema-conformant JSON (theme_pack_to_dict /
   theme_pack_from_dict) plus an asset manifest so Phase 2 (docs website)
   and Phase 3 (devtool app) can consume the same packs later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.schema import ThemePack, ThemeSchemaError
from gui.src.theming.storage import (
    import_asset,
    missing_assets,
    theme_pack_from_dict,
    theme_pack_to_dict,
)

#: The file the editor targets -- same path load_user_qss_override reads.
USER_QSS_PATH = Path.home() / ".image-toolkit" / "user_theme.qss"


class QssEditorWidget(QWidget):
    """Expert-mode live QSS editor for ~/.image-toolkit/user_theme.qss.

    Unrestricted (expert) mode is off by default; the editor only reads
    the file until the user explicitly enables the toggle (round-2 answer:
    safe styling mode is the default, raw QSS is the escape hatch).
    """

    def __init__(self, parent=None, *, qss_path: Optional[Path] = None) -> None:
        super().__init__(parent)
        self.qss_path = Path(qss_path) if qss_path is not None else USER_QSS_PATH
        self._build_ui()
        self._refresh_toggle_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Advanced: raw QSS override (expert mode)"))
        header.addStretch()
        self.unrestricted_check = QCheckBox("Enable unrestricted QSS editing")
        self.unrestricted_check.toggled.connect(self._refresh_toggle_state)
        header.addWidget(self.unrestricted_check)
        root.addLayout(header)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("/* QSS appended after the generated theme. Empty = default styling. */")
        self.editor.setReadOnly(True)
        root.addWidget(self.editor, 1)

        actions = QHBoxLayout()
        self.reload_button = QPushButton("Reload from disk")
        self.reload_button.clicked.connect(self.load_from_disk)
        self.apply_button = QPushButton("Apply live")
        self.apply_button.clicked.connect(self.save_and_apply)
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)
        actions.addWidget(self.reload_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.reset_button)
        actions.addStretch()
        root.addLayout(actions)

    def _refresh_toggle_state(self, *_args) -> None:
        enabled = self.unrestricted_check.isChecked()
        self.editor.setReadOnly(not enabled)
        self.apply_button.setEnabled(enabled)

    def load_from_disk(self) -> None:
        try:
            text = self.qss_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        self.editor.setPlainText(text)

    def save_and_apply(self) -> bool:
        """Persist the editor contents and signal for a re-apply.

        Returns True on success. The caller (settings window / main
        window) is responsible for actually re-applying the theme so the
        override hook picks up the new file.
        """
        if not self.unrestricted_check.isChecked():
            QMessageBox.information(self, "Read-only", "Enable unrestricted QSS editing first.")
            return False
        self.qss_path.parent.mkdir(parents=True, exist_ok=True)
        self.qss_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        return True

    def reset_to_default(self) -> None:
        """Remove the override file entirely (safe default styling)."""
        if self.qss_path.exists():
            self.qss_path.unlink()
        self.editor.setPlainText("")
        self.load_from_disk()


# ---------------------------------------------------------------------------
# Cross-surface theme export/import
# ---------------------------------------------------------------------------


def export_theme_pack(pack: ThemePack, dest: Path) -> Path:
    """Write a portable theme-pack JSON file.

    The JSON is the canonical theme_pack_to_dict form (the same shape the
    docs website / devtool app will read in Phases 2/3), plus an
    ``asset_manifest`` listing every imported background asset_id so an
    importer can tell the user which images must travel with the pack
    (linked-path refs travel by path, per the round-2 answer).
    """
    dest = Path(dest)
    payload = theme_pack_to_dict(pack)
    payload["asset_manifest"] = [
        ref.asset_id
        for bg in pack.backgrounds
        for ref in bg.images
        if ref.kind == "imported" and ref.asset_id
    ]
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return dest


def import_theme_pack(path: Path) -> ThemePack:
    """Load a theme pack from an exported JSON file (schema-conformant)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.pop("asset_manifest", None)
    try:
        return theme_pack_from_dict(data)
    except ThemeSchemaError as exc:
        raise ThemeSchemaError(f"invalid theme pack {path}: {exc}") from exc


def import_background_asset(source_path: str) -> str:
    """Copy a background image into managed storage; returns the asset_id."""
    return import_asset(Path(source_path))


def check_missing_assets(pack: ThemePack) -> list:
    """Every background reference in *pack* that can't be resolved now."""
    return missing_assets(pack)


__all__ = [
    "USER_QSS_PATH",
    "QssEditorWidget",
    "check_missing_assets",
    "export_theme_pack",
    "import_background_asset",
    "import_theme_pack",
]
