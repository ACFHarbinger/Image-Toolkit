"""Connection/statistics UI section builder for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass


def build_connection_section(tab: Any, main_layout: QVBoxLayout) -> None:
    """Build the "Unified Library" connection/statistics section onto tab."""
    conn_group = QGroupBox("Unified Library (encrypted, opens with the vault)")
    conn_layout = QVBoxLayout(conn_group)

    tab.button_conn_layout = QHBoxLayout()
    tab.btn_connect = QPushButton("🔓 Open Library")
    tab.btn_connect.setToolTip(
        "Open the unified library database (requires an unlocked vault). "
        "Normally this happens automatically at login."
    )
    apply_shadow_effect(
        tab.btn_connect, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_connect.clicked.connect(tab.connect_database)
    tab.button_conn_layout.addWidget(tab.btn_connect)

    tab.btn_reset_db = QPushButton("⚠️ Reset Database (Drop All Data)")
    tab.btn_reset_db.setObjectName("btn_danger")
    apply_shadow_effect(
        tab.btn_reset_db, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_reset_db.clicked.connect(tab.reset_database)
    tab.btn_reset_db.hide()
    tab.button_conn_layout.addWidget(tab.btn_reset_db)

    # Management Buttons
    tab.btn_vacuum = QPushButton("🧹 Vacuum Database")
    apply_shadow_effect(
        tab.btn_vacuum, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_vacuum.clicked.connect(tab.run_vacuum)
    tab.btn_vacuum.hide()
    tab.button_conn_layout.addWidget(tab.btn_vacuum)

    tab.btn_reindex = QPushButton("🔍 Reindex Database")
    apply_shadow_effect(
        tab.btn_reindex, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_reindex.clicked.connect(tab.run_reindex)
    tab.btn_reindex.hide()
    tab.button_conn_layout.addWidget(tab.btn_reindex)

    tab.btn_embed_backfill = QPushButton("🧠 Embed Unembedded Images")
    tab.btn_embed_backfill.setToolTip(
        "Compute semantic (open_clip) embeddings for images that don't "
        "have one yet, enabling text/find-similar search (DB.7)."
    )
    apply_shadow_effect(
        tab.btn_embed_backfill, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_embed_backfill.clicked.connect(tab.run_embed_backfill)
    tab.btn_embed_backfill.hide()
    tab.button_conn_layout.addWidget(tab.btn_embed_backfill)

    tab.btn_check_postgres = QPushButton("🐘 Check PostgreSQL")
    tab.btn_check_postgres.setToolTip(
        "Check external PostgreSQL + pgvector connection status (optional prerequisite for vector search).\n"
        "The app operates normally on local SQLCipher storage."
    )
    apply_shadow_effect(
        tab.btn_check_postgres, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_check_postgres.clicked.connect(tab.check_postgres_status)
    tab.button_conn_layout.addWidget(tab.btn_check_postgres)

    conn_layout.addLayout(tab.button_conn_layout)

    from gui.src.helpers.database.postgres_check import load_postgres_config

    postgres_config = load_postgres_config(tab.vault_manager)
    try:
        postgres_port = int(postgres_config.get("DB_PORT", 5432))
    except (TypeError, ValueError):
        postgres_port = 5432
    postgres_group = QGroupBox("External PostgreSQL + pgvector (optional)")
    postgres_layout = QVBoxLayout(postgres_group)
    postgres_form = QFormLayout()

    tab.postgres_host_edit = QLineEdit(postgres_config.get("DB_HOST", "localhost"))
    tab.postgres_port_spin = QSpinBox()
    tab.postgres_port_spin.setRange(1, 65535)
    tab.postgres_port_spin.setValue(postgres_port)
    tab.postgres_db_edit = QLineEdit(postgres_config.get("DB_NAME", "image_toolkit"))
    tab.postgres_user_edit = QLineEdit(postgres_config.get("DB_USER", "toolkit_user"))
    tab.postgres_password_edit = QLineEdit()
    tab.postgres_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
    tab.postgres_password_edit.setPlaceholderText("Saved securely in vault")

    postgres_form.addRow("Host:", tab.postgres_host_edit)
    postgres_form.addRow("Port:", tab.postgres_port_spin)
    postgres_form.addRow("Database:", tab.postgres_db_edit)
    postgres_form.addRow("User:", tab.postgres_user_edit)
    postgres_form.addRow("Password:", tab.postgres_password_edit)
    postgres_layout.addLayout(postgres_form)

    postgres_buttons = QHBoxLayout()
    tab.btn_save_postgres = QPushButton("Save Connection")
    tab.btn_save_postgres.clicked.connect(tab.save_postgres_settings)
    postgres_buttons.addWidget(tab.btn_save_postgres)
    tab.btn_clear_postgres_password = QPushButton("Clear Saved Password")
    tab.btn_clear_postgres_password.clicked.connect(tab.clear_postgres_password)
    postgres_buttons.addWidget(tab.btn_clear_postgres_password)
    postgres_buttons.addStretch()
    postgres_layout.addLayout(postgres_buttons)
    conn_layout.addWidget(postgres_group)
    main_layout.addWidget(conn_group)

    # Statistics display
    tab.stats_label = QLabel("Not connected to database")
    main_layout.addWidget(tab.stats_label)


class DatabaseConnectionUIBuilder:
    """Builder for the connection section."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def build(self, main_layout: QVBoxLayout) -> None:
        build_connection_section(self.tab, main_layout)


class _UIConnectionMixin:
    """Backward-compatible mixin adapter."""

    def _build_connection_section(self, main_layout: QVBoxLayout) -> None:
        build_connection_section(self, main_layout)


__all__ = ["DatabaseConnectionUIBuilder", "_UIConnectionMixin", "build_connection_section"]
