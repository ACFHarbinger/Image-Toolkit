"""Embedding-mode and search-scope config change handlers.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.web.recon.config import EMBED_FACE, SCOPE_BOTH, SCOPE_LOCAL, SCOPE_WEB
from PySide6.QtWidgets import QMessageBox

from ._tab_bound import TabBoundController


class EntityReconConfigController(TabBoundController):
    """Pushes embed-mode/search-scope combo changes onto the ReconConfig."""

    def _on_embed_changed(self, _idx: int):
        self._config.embed_mode = self.embed_combo.currentData()
        if self._engine is not None:
            self._engine.config = self._config

    def _apply_scope(self, scope: str):
        """Push a discovery scope onto the config, keeping the legacy
        ``privacy_mode`` network gate in sync (offline only for local scope)."""
        self._config.search_scope = scope
        self._config.privacy_mode = scope == SCOPE_LOCAL
        if self._engine is not None:
            self._engine.config = self._config

    def _on_scope_changed(self, _idx: int):
        scope = self.scope_combo.currentData()
        self._apply_scope(scope)
        msg = {
            SCOPE_LOCAL: "Search scope: Local only — offline, local index only.",
            SCOPE_WEB: "Search scope: Web only — reverse-image web discovery.",
            SCOPE_BOTH: "Search scope: Local + Web — local first, web fallback.",
        }.get(scope, "Search scope updated.")
        self._set_status(msg)

    # ------------------------------------------------------------------
    # TabConfig contract (R1.2 / #557)
    # ------------------------------------------------------------------
    def collect(self) -> dict:
        return {
            "dataset_root": self.dataset_edit.text().strip() or None,
            "embed_mode": self.embed_combo.currentData(),
            "search_scope": self.scope_combo.currentData(),
            "batch_target_dir": self.target_edit.text().strip() or None,
        }

    def get_default_config(self) -> dict:
        return {
            "dataset_root": "",
            "embed_mode": EMBED_FACE,
            "search_scope": SCOPE_LOCAL,
            "batch_target_dir": "",
        }

    def set_config(self, config: dict):
        try:
            self.dataset_edit.setText(config.get("dataset_root") or "")

            # setCurrentIndex fires the change handlers, so the restored
            # values land on the ReconConfig through the same path as a
            # manual pick (single source of truth).
            embed_idx = self.embed_combo.findData(config.get("embed_mode"))
            if embed_idx != -1:
                self.embed_combo.setCurrentIndex(embed_idx)

            scope_idx = self.scope_combo.findData(config.get("search_scope"))
            if scope_idx != -1:
                self.scope_combo.setCurrentIndex(scope_idx)

            self.target_edit.setText(config.get("batch_target_dir") or "")
            print("EntityReconTab configuration loaded.")
        except Exception as e:
            print(f"Error applying EntityReconTab config: {e}")
            QMessageBox.warning(self.tab, "Config Error", f"Failed to apply some settings: {e}")


__all__ = ["EntityReconConfigController"]
