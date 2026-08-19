"""Connection/statistics UI section builder for ``DatabaseTab``.

Extracted from ``DatabaseTab.__init__`` -- pure code motion, no logic change,
to keep the file under the codebase's 500-code-line convention (§5.17).
"""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ....styles import apply_shadow_effect


class _UIConnectionMixin:
    """Builds the "Unified Library" connection/statistics section."""

    def _build_connection_section(self, main_layout) -> None:
        conn_group = QGroupBox("Unified Library (encrypted, opens with the vault)")
        conn_layout = QVBoxLayout(conn_group)

        self.button_conn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("🔓 Open Library")
        self.btn_connect.setToolTip(
            "Open the unified library database (requires an unlocked vault). "
            "Normally this happens automatically at login."
        )
        apply_shadow_effect(
            self.btn_connect, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_connect.clicked.connect(self.connect_database)
        self.button_conn_layout.addWidget(self.btn_connect)

        self.btn_reset_db = QPushButton("⚠️ Reset Database (Drop All Data)")
        self.btn_reset_db.setObjectName("btn_danger")
        apply_shadow_effect(
            self.btn_reset_db, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_reset_db.clicked.connect(self.reset_database)
        self.btn_reset_db.hide()
        self.button_conn_layout.addWidget(self.btn_reset_db)

        # Management Buttons
        self.btn_vacuum = QPushButton("🧹 Vacuum Database")
        apply_shadow_effect(
            self.btn_vacuum, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_vacuum.clicked.connect(self.run_vacuum)
        self.btn_vacuum.hide()
        self.button_conn_layout.addWidget(self.btn_vacuum)

        self.btn_reindex = QPushButton("🔍 Reindex Database")
        apply_shadow_effect(
            self.btn_reindex, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_reindex.clicked.connect(self.run_reindex)
        self.btn_reindex.hide()
        self.button_conn_layout.addWidget(self.btn_reindex)

        self.btn_embed_backfill = QPushButton("🧠 Embed Unembedded Images")
        self.btn_embed_backfill.setToolTip(
            "Compute semantic (open_clip) embeddings for images that don't "
            "have one yet, enabling text/find-similar search (DB.7)."
        )
        apply_shadow_effect(
            self.btn_embed_backfill, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_embed_backfill.clicked.connect(self.run_embed_backfill)
        self.btn_embed_backfill.hide()
        self.button_conn_layout.addWidget(self.btn_embed_backfill)

        conn_layout.addLayout(self.button_conn_layout)
        main_layout.addWidget(conn_group)

        # Statistics display
        self.stats_label = QLabel("Not connected to database")
        main_layout.addWidget(self.stats_label)


__all__ = ["_UIConnectionMixin"]
