"""Status-bar text and busy-state (progress bar / button lock) helpers.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations


class _StatusHelpersMixin:
    """Small helpers for updating the status label and busy button state."""

    def _set_status(self, msg: str):
        self.status_label.setText(msg)

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        self.btn_build.setEnabled(not busy)
        self.btn_resolve.setEnabled(not busy)


__all__ = ["_StatusHelpersMixin"]
