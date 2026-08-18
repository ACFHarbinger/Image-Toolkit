"""Embedding-mode and search-scope config change handlers.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.web.recon.config import SCOPE_BOTH, SCOPE_LOCAL, SCOPE_WEB


class _ConfigMixin:
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


__all__ = ["_ConfigMixin"]
