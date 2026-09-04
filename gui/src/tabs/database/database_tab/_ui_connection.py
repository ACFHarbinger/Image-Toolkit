"""Connection/statistics UI section builder for ``DatabaseTab``.

Extracted from ``DatabaseTab.__init__`` -- pure code motion, no logic change,
to keep the file under the codebase's 500-code-line convention (§5.17).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

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

        self.btn_check_postgres = QPushButton("🐘 Check PostgreSQL")
        self.btn_check_postgres.setToolTip(
            "Check external PostgreSQL + pgvector connection status (optional prerequisite for vector search).\n"
            "The app operates normally on local SQLCipher storage."
        )
        apply_shadow_effect(
            self.btn_check_postgres, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_check_postgres.clicked.connect(self.check_postgres_status)
        self.button_conn_layout.addWidget(self.btn_check_postgres)

        conn_layout.addLayout(self.button_conn_layout)

        from gui.src.helpers.database.postgres_check import load_postgres_config

        postgres_config = load_postgres_config(self.vault_manager)
        try:
            postgres_port = int(postgres_config.get("DB_PORT", 5432))
        except (TypeError, ValueError):
            postgres_port = 5432
        postgres_group = QGroupBox("External PostgreSQL + pgvector (optional)")
        postgres_layout = QVBoxLayout(postgres_group)
        postgres_form = QFormLayout()

        self.postgres_host_edit = QLineEdit(postgres_config.get("DB_HOST", "localhost"))
        self.postgres_port_spin = QSpinBox()
        self.postgres_port_spin.setRange(1, 65535)
        self.postgres_port_spin.setValue(postgres_port)
        self.postgres_db_edit = QLineEdit(postgres_config.get("DB_NAME", "image_toolkit"))
        self.postgres_user_edit = QLineEdit(postgres_config.get("DB_USER", "toolkit_user"))
        self.postgres_password_edit = QLineEdit()
        self.postgres_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.postgres_password_edit.setPlaceholderText("Saved securely in vault")

        postgres_form.addRow("Host:", self.postgres_host_edit)
        postgres_form.addRow("Port:", self.postgres_port_spin)
        postgres_form.addRow("Database:", self.postgres_db_edit)
        postgres_form.addRow("User:", self.postgres_user_edit)
        postgres_form.addRow("Password:", self.postgres_password_edit)
        postgres_layout.addLayout(postgres_form)

        postgres_buttons = QHBoxLayout()
        self.btn_save_postgres = QPushButton("Save Connection")
        self.btn_save_postgres.clicked.connect(self.save_postgres_settings)
        postgres_buttons.addWidget(self.btn_save_postgres)
        self.btn_clear_postgres_password = QPushButton("Clear Saved Password")
        self.btn_clear_postgres_password.clicked.connect(self.clear_postgres_password)
        postgres_buttons.addWidget(self.btn_clear_postgres_password)
        postgres_buttons.addStretch()
        postgres_layout.addLayout(postgres_buttons)
        conn_layout.addWidget(postgres_group)
        main_layout.addWidget(conn_group)

        # Statistics display
        self.stats_label = QLabel("Not connected to database")
        main_layout.addWidget(self.stats_label)


__all__ = ["_UIConnectionMixin"]
