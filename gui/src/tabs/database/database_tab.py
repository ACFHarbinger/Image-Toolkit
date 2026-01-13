import os
import json
import psycopg2

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox,
    QComboBox,
    QInputDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QAbstractItemView,
    QMenu,
    QProgressDialog,
    QLineEdit,
    QPushButton,
    QLabel,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QScrollArea,
    QGroupBox,
    QWidget,
    QFileDialog,
)
from dotenv import load_dotenv
from backend.src.core import PgvectorImageDatabase as ImageDatabase
from backend.src.utils.definitions import LOCAL_SOURCE_PATH
from ...styles.style import apply_shadow_effect


class DatabaseTab(QWidget):
    """
    Manages PostgreSQL connection, statistics display, and tag/group population.
    """

    def __init__(self, env_path="env/vars.env"):
        super().__init__()
        self.db: Optional[ImageDatabase] = None

        # --- Tab References ---
        # These are assigned by MainWindow after all tabs are initialized
        self.scan_tab_ref = None
        self.search_tab_ref = None
        self.merge_tab_ref = None
        self.delete_tab_ref = None
        self.wallpaper_tab_ref = None

        self.old_edit_value = None

        main_layout = QVBoxLayout(self)

        # --- PostgreSQL Connection Section ---
        conn_group = QGroupBox("PostgreSQL Connection Details")
        conn_form_layout = QFormLayout()

        load_dotenv(dotenv_path=env_path)
        self.db_host = QLineEdit(os.getenv("DB_HOST"))
        self.db_port = QLineEdit(os.getenv("DB_PORT"))
        self.db_user = QLineEdit(os.getenv("DB_USER"))
        self.db_password = QLineEdit(os.getenv("DB_PASSWORD"))
        self.db_password.setEchoMode(QLineEdit.Password)
        self.db_name = QLineEdit(
            os.getenv("DB_NAME"),
        )

        conn_form_layout.addRow("Host:", self.db_host)
        conn_form_layout.addRow("Port:", self.db_port)
        conn_form_layout.addRow("User:", self.db_user)
        conn_form_layout.addRow("Password:", self.db_password)
        conn_form_layout.addRow("Database Name:", self.db_name)

        conn_layout = QVBoxLayout(conn_group)
        conn_layout.addLayout(conn_form_layout)

        self.button_conn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect to PostgreSQL")
        apply_shadow_effect(
            self.btn_connect, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_connect.clicked.connect(self.connect_database)
        self.button_conn_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect from PostgreSQL")
        self.btn_disconnect.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 10px;"
        )
        apply_shadow_effect(
            self.btn_disconnect, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_disconnect.clicked.connect(self.disconnect_database)
        self.btn_disconnect.hide()
        self.button_conn_layout.addWidget(self.btn_disconnect)

        self.btn_reset_db = QPushButton("⚠️ Reset Database (Drop All Data)")
        self.btn_reset_db.setStyleSheet(
            "background-color: #c0392b; color: white; padding: 10px; font-weight: bold;"
        )
        apply_shadow_effect(
            self.btn_reset_db, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_reset_db.clicked.connect(self.reset_database)
        self.btn_reset_db.hide()
        self.button_conn_layout.addWidget(self.btn_reset_db)

        # Maintenance Buttons
        self.btn_vacuum = QPushButton("🧹 Vacuum Database")
        self.btn_vacuum.setStyleSheet("background-color: #8e44ad; color: white; padding: 10px;")
        apply_shadow_effect(self.btn_vacuum, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_vacuum.clicked.connect(self.run_vacuum)
        self.btn_vacuum.hide()
        self.button_conn_layout.addWidget(self.btn_vacuum)

        self.btn_reindex = QPushButton("🔍 Reindex Database")
        self.btn_reindex.setStyleSheet("background-color: #2980b9; color: white; padding: 10px;")
        apply_shadow_effect(self.btn_reindex, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_reindex.clicked.connect(self.run_reindex)
        self.btn_reindex.hide()
        self.button_conn_layout.addWidget(self.btn_reindex)

        conn_layout.addLayout(self.button_conn_layout)
        main_layout.addWidget(conn_group)

        # Statistics display
        self.stats_label = QLabel("Not connected to database")
        self.stats_label.setStyleSheet(
            "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
        )
        main_layout.addWidget(self.stats_label)

        # --- Populate Database Section ---
        self.populate_group = QGroupBox("Populate Database")
        populate_layout = QVBoxLayout(self.populate_group)

        # -------------------------------------------------------------
        # Auto-Populate Button
        # -------------------------------------------------------------
        auto_pop_group = QGroupBox("Automatic Population")
        auto_pop_layout = QVBoxLayout(auto_pop_group)

        lbl_auto_info = QLabel(
            f"Scans <b>{LOCAL_SOURCE_PATH}</b>.<br>Top-level folders become Groups. Second-level folders become Subgroups."
        )
        lbl_auto_info.setStyleSheet("color: #aaa; font-style: italic;")
        auto_pop_layout.addWidget(lbl_auto_info)

        self.btn_auto_populate = QPushButton(
            "Auto-Sync Groups and Subgroups from Source"
        )
        self.btn_auto_populate.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 8px; font-weight: bold;"
        )
        apply_shadow_effect(
            self.btn_auto_populate,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_auto_populate.clicked.connect(self.auto_populate_from_source)
        auto_pop_layout.addWidget(self.btn_auto_populate)

        populate_layout.addWidget(auto_pop_group)
        # -------------------------------------------------------------

        # --- Create New Group section ---
        create_group_group = QGroupBox("Create Group(s)")
        create_group_layout = QFormLayout(create_group_group)

        self.new_group_name_edit = QLineEdit()
        self.new_group_name_edit.setPlaceholderText(
            "group1, group2, group3 ... (comma-separated)"
        )
        create_group_layout.addRow("Group Name(s):", self.new_group_name_edit)

        self.btn_create_group = QPushButton("Create Group(s)")
        apply_shadow_effect(
            self.btn_create_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_create_group.clicked.connect(self.create_new_group)
        create_group_layout.addRow(self.btn_create_group)

        self.new_group_name_edit.returnPressed.connect(self.btn_create_group.click)
        populate_layout.addWidget(create_group_group)

        # --- Existing Groups section ---
        existing_groups_group = QGroupBox("Existing Groups")
        existing_groups_layout = QVBoxLayout(existing_groups_group)

        groups_btn_layout = QHBoxLayout()
        self.btn_refresh_groups = QPushButton("Refresh List")
        apply_shadow_effect(
            self.btn_refresh_groups,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_refresh_groups.clicked.connect(self.refresh_groups_list)
        groups_btn_layout.addWidget(self.btn_refresh_groups)

        self.btn_remove_group = QPushButton("Remove Selected Group")
        self.btn_remove_group.setStyleSheet("background-color: #f39c12; color: white;")
        apply_shadow_effect(
            self.btn_remove_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_remove_group.clicked.connect(self.remove_selected_group)
        groups_btn_layout.addWidget(self.btn_remove_group)
        existing_groups_layout.addLayout(groups_btn_layout)

        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(1)
        self.groups_table.setHorizontalHeaderLabels(["Group Name"])
        self.groups_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.groups_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.groups_table.setStyleSheet(
            """
            QTableWidget { 
                background-color: #36393f; 
                border: 1px solid #4f545c;
                alternate-background-color: #3b3e44;
            }
            QHeaderView::section { 
                background-color: #4f545c; 
                color: white; 
                padding: 4px; 
                border: 1px solid #36393f;
            }
        """
        )
        self.groups_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.groups_table.setMinimumHeight(200)

        self.groups_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.groups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups_table.customContextMenuRequested.connect(
            self.show_group_context_menu
        )
        self.groups_table.cellPressed.connect(self.store_old_value)
        self.groups_table.itemChanged.connect(self.handle_group_edited)

        existing_groups_layout.addWidget(self.groups_table)
        populate_layout.addWidget(existing_groups_group)

        # --- Create New Subgroup section ---
        create_subgroup_group = QGroupBox("Create Subgroup(s)")
        create_subgroup_layout = QFormLayout(create_subgroup_group)

        self.new_subgroup_parent_combo = QComboBox()
        self.new_subgroup_parent_combo.setPlaceholderText("Select Parent Group...")
        self.new_subgroup_parent_combo.setEditable(True)
        create_subgroup_layout.addRow("Parent Group:", self.new_subgroup_parent_combo)

        self.new_subgroup_name_edit = QLineEdit()
        self.new_subgroup_name_edit.setPlaceholderText(
            "subgroup1, subgroup2 ... (comma-separated)"
        )
        create_subgroup_layout.addRow("Subgroup Name(s):", self.new_subgroup_name_edit)

        self.btn_create_subgroup = QPushButton("Create Subgroup(s)")
        apply_shadow_effect(
            self.btn_create_subgroup,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_create_subgroup.clicked.connect(self.create_new_subgroup)
        create_subgroup_layout.addRow(self.btn_create_subgroup)

        self.new_subgroup_name_edit.returnPressed.connect(
            self.btn_create_subgroup.click
        )
        populate_layout.addWidget(create_subgroup_group)

        # --- Existing Subgroups section ---
        existing_subgroups_group = QGroupBox("Existing Subgroups")
        existing_subgroups_layout = QVBoxLayout(existing_subgroups_group)

        existing_subgroups_filter_layout = QHBoxLayout()
        existing_subgroups_filter_layout.addWidget(QLabel("Filter by Group:"))
        self.existing_subgroups_filter_combo = QComboBox()
        self.existing_subgroups_filter_combo.setPlaceholderText(
            "Select Group to View..."
        )
        existing_subgroups_filter_layout.addWidget(self.existing_subgroups_filter_combo)
        existing_subgroups_layout.addLayout(existing_subgroups_filter_layout)

        self.existing_subgroups_filter_combo.currentTextChanged.connect(
            self.refresh_subgroups_list
        )

        subgroups_btn_layout = QHBoxLayout()
        self.btn_refresh_subgroups = QPushButton("Refresh Group Filters")
        apply_shadow_effect(
            self.btn_refresh_subgroups,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_refresh_subgroups.clicked.connect(self._refresh_all_group_combos)
        subgroups_btn_layout.addWidget(self.btn_refresh_subgroups)

        self.btn_remove_subgroup = QPushButton("Remove Selected Subgroup")
        self.btn_remove_subgroup.setStyleSheet(
            "background-color: #f39c12; color: white;"
        )
        apply_shadow_effect(
            self.btn_remove_subgroup,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_remove_subgroup.clicked.connect(self.remove_selected_subgroup)
        subgroups_btn_layout.addWidget(self.btn_remove_subgroup)
        existing_subgroups_layout.addLayout(subgroups_btn_layout)

        self.subgroups_table = QTableWidget()
        self.subgroups_table.setColumnCount(2)
        self.subgroups_table.setHorizontalHeaderLabels(
            ["Subgroup Name", "Parent Group"]
        )
        self.subgroups_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.subgroups_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.subgroups_table.setAlternatingRowColors(True)
        self.subgroups_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.subgroups_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.subgroups_table.setStyleSheet(self.groups_table.styleSheet())
        self.subgroups_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.subgroups_table.setMinimumHeight(200)

        self.subgroups_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.subgroups_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.subgroups_table.customContextMenuRequested.connect(
            self.show_subgroup_context_menu
        )
        self.subgroups_table.cellPressed.connect(self.store_old_value)
        self.subgroups_table.itemChanged.connect(self.handle_subgroup_edited)

        existing_subgroups_layout.addWidget(self.subgroups_table)
        populate_layout.addWidget(existing_subgroups_group)

        # --- Create New Tag section ---
        create_tag_group = QGroupBox("Create/Update Tag(s)")
        create_tag_layout = QFormLayout(create_tag_group)

        self.new_tag_name_edit = QLineEdit()
        self.new_tag_name_edit.setPlaceholderText(
            "tag1, tag2, tag3 ... (comma-separated)"
        )
        create_tag_layout.addRow("Tag Name(s):", self.new_tag_name_edit)

        self.new_tag_type_combo = QComboBox()
        self.new_tag_type_combo.setEditable(True)
        self.new_tag_type_combo.addItems(
            ["", "Artist", "Series", "Character", "General", "Meta"]
        )
        self.new_tag_type_combo.setPlaceholderText(
            "e.g., Artist, Character, General (Optional)"
        )
        create_tag_layout.addRow("Tag Type (applies to all):", self.new_tag_type_combo)

        self.btn_create_tag = QPushButton("Create/Update Tag(s)")
        apply_shadow_effect(
            self.btn_create_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_create_tag.clicked.connect(self.create_new_tag)
        create_tag_layout.addRow(self.btn_create_tag)

        self.new_tag_name_edit.returnPressed.connect(self.btn_create_tag.click)
        self.new_tag_type_combo.lineEdit().returnPressed.connect(
            self.btn_create_tag.click
        )

        populate_layout.addWidget(create_tag_group)

        # -------------------------------------------------------------
        # Bulk Tag Import Section
        # -------------------------------------------------------------
        bulk_import_group = QGroupBox("Bulk Tag Import from JSON")
        bulk_import_layout = QFormLayout(bulk_import_group)

        self.bulk_tag_type_combo = QComboBox()
        self.bulk_tag_type_combo.setEditable(True)
        self.bulk_tag_type_combo.addItems(
            ["", "Artist", "Series", "Character", "General", "Meta"]
        )
        self.bulk_tag_type_combo.setPlaceholderText("Tag Type to apply (e.g., Artist)")
        bulk_import_layout.addRow("Tag Type:", self.bulk_tag_type_combo)

        self.json_file_path_edit = QLineEdit()
        self.json_file_path_edit.setPlaceholderText(
            "Select JSON file containing a 'tags' array..."
        )

        btn_browse_json = QPushButton("Browse JSON")
        btn_browse_json.clicked.connect(self.browse_json_file)

        json_h_layout = QHBoxLayout()
        json_h_layout.addWidget(self.json_file_path_edit)
        json_h_layout.addWidget(btn_browse_json)
        bulk_import_layout.addRow("JSON File:", json_h_layout)

        self.btn_import_tags = QPushButton("Import Tags from JSON")
        self.btn_import_tags.setStyleSheet(
            "background-color: #3498db; color: white; padding: 8px;"
        )
        apply_shadow_effect(
            self.btn_import_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_import_tags.clicked.connect(self.import_tags_from_json)
        bulk_import_layout.addRow(self.btn_import_tags)

        populate_layout.addWidget(bulk_import_group)
        # -------------------------------------------------------------

        # --- Existing Tags section ---
        existing_tags_group = QGroupBox("Existing Tags")
        existing_tags_layout = QVBoxLayout(existing_tags_group)

        tags_btn_layout = QHBoxLayout()
        self.btn_refresh_tags = QPushButton("Refresh List")
        apply_shadow_effect(
            self.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_tags.clicked.connect(self.refresh_tags_list)
        tags_btn_layout.addWidget(self.btn_refresh_tags)

        self.btn_remove_tag = QPushButton("Remove Selected Tag")
        self.btn_remove_tag.setStyleSheet("background-color: #f39c12; color: white;")
        apply_shadow_effect(
            self.btn_remove_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_remove_tag.clicked.connect(self.remove_selected_tag)
        tags_btn_layout.addWidget(self.btn_remove_tag)
        existing_tags_layout.addLayout(tags_btn_layout)

        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(2)
        self.tags_table.setHorizontalHeaderLabels(["Tag Name", "Tag Type"])
        self.tags_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tags_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tags_table.setAlternatingRowColors(True)
        self.tags_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tags_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tags_table.setStyleSheet(self.groups_table.styleSheet())
        self.tags_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.tags_table.setMinimumHeight(200)

        self.tags_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tags_table.customContextMenuRequested.connect(self.show_tag_context_menu)
        self.tags_table.cellPressed.connect(self.store_old_value)
        self.tags_table.itemChanged.connect(self.handle_tag_edited)

        existing_tags_layout.addWidget(self.tags_table)
        populate_layout.addWidget(existing_tags_group)

        populate_scroll_area = QScrollArea()
        populate_scroll_area.setWidgetResizable(True)
        populate_scroll_area.setWidget(self.populate_group)
        populate_scroll_area.setStyleSheet("QScrollArea { border: none; }")

        main_layout.addWidget(populate_scroll_area)

        self.update_button_states(connected=False)

    # --- Connection and Statistics Methods ---

    def connect_database(self):
        try:
            db_host = self.db_host.text().strip()
            db_port = self.db_port.text().strip()
            db_user = self.db_user.text().strip()
            db_password = self.db_password.text()
            db_name = self.db_name.text().strip()
            if not all([db_host, db_port, db_user, db_name]):
                QMessageBox.warning(
                    self, "Error", "All connection fields are required."
                )
                return

            if self.db:
                self.db.close()

            self.db = ImageDatabase(
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                db_host=db_host,
                db_port=db_port,
                embed_dim=128,
            )
            self.update_statistics()
            self.update_button_states(connected=True)
            self._refresh_all_group_combos()
            self.refresh_subgroup_autocomplete()
            self.refresh_tags_list()
            self.refresh_groups_list()
            self.refresh_subgroups_list()

            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()

            QMessageBox.information(
                self, "Success", f"Connected to PostgreSQL DB: {db_name}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to connect to database:\n{str(e)}"
            )
            self.update_button_states(connected=False)
            self.stats_label.setText("Connection Failed")
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
            )

    def disconnect_database(self):
        if not self.db:
            return
        try:
            self.db.close()
            self.db = None
            self.update_button_states(connected=False)

            self.stats_label.setText("Not connected to database")
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
            )

            self.tags_table.setRowCount(0)
            self.groups_table.setRowCount(0)
            self.subgroups_table.setRowCount(0)

            self.new_subgroup_parent_combo.clear()
            self.existing_subgroups_filter_combo.clear()

            if self.search_tab_ref:
                if hasattr(self.search_tab_ref, "group_combo"):
                    self.search_tab_ref.group_combo.clear()
                if hasattr(self.search_tab_ref, "subgroup_combo"):
                    self.search_tab_ref.subgroup_combo.clear()

            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()

            QMessageBox.information(
                self, "Disconnected", "Successfully disconnected from the database."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error during disconnection:\n{str(e)}"
            )

    def reset_database(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        confirm1 = QMessageBox.question(
            self,
            "Confirm Destructive Action",
            "Are you absolutely sure you want to reset the database?\n\n"
            "ALL DATA (images, tags, groups, subgroups) will be PERMANENTLY DELETED.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm1 == QMessageBox.No:
            QMessageBox.information(self, "Cancelled", "Database reset was cancelled.")
            return

        text, ok = QInputDialog.getText(
            self,
            "Final Confirmation",
            "This is your final warning. This action cannot be undone.\n"
            "This will DROP all tables and recreate the schema.\n\n"
            "Type 'RESET' in the box below to proceed:",
        )

        if not ok:
            QMessageBox.information(self, "Cancelled", "Database reset was cancelled.")
            return

        if text.strip() != "RESET":
            QMessageBox.warning(
                self,
                "Cancelled",
                "Input did not match 'RESET'. Database reset was cancelled.",
            )
            return

        try:
            self.db.reset_database()
            QMessageBox.information(
                self, "Success", "Database has been reset successfully."
            )

            self.update_statistics()
            self._refresh_all_group_combos()
            self.refresh_subgroup_autocomplete()
            self.refresh_tags_list()
            self.refresh_groups_list()
            self.refresh_subgroups_list()

            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset database:\n{str(e)}")

    def update_statistics(self):
        if not self.db:
            return
        try:
            stats = self.db.get_statistics()
            
            # Format file size
            total_bytes = stats.get('total_file_size', 0)
            if total_bytes < 1024:
                size_str = f"{total_bytes} B"
            elif total_bytes < 1024**2:
                size_str = f"{total_bytes/1024:.2f} KB"
            elif total_bytes < 1024**3:
                size_str = f"{total_bytes/1024**2:.2f} MB"
            else:
                size_str = f"{total_bytes/1024**3:.2f} GB"

            last_sync = stats.get('last_sync_date')
            last_sync_str = last_sync.strftime("%Y-%m-%d %H:%M:%S") if last_sync else "Never"

            stats_text = (
                f"📊 Database Statistics:\n"
                f"Images: {stats.get('total_images', 0)} ({size_str}) | "
                f"Tags: {stats.get('total_tags', 0)} | "
                f"Groups: {stats.get('total_groups', 0)} | "
                f"Subgroups: {stats.get('total_subgroups', 0)}\n"
                f"Last Sync: {last_sync_str}"
            )
            self.stats_label.setText(stats_text)
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #27ae60; color: white; border-radius: 5px; font-weight: bold;"
            )
        except Exception as e:
            self.stats_label.setText(f"Error getting statistics: {str(e)}")
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
            )

    def run_vacuum(self):
        if not self.db: return
        try:
            self.db.maintenance_vacuum(full=False)
            QMessageBox.information(self, "Success", "Database vacuum completed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Vacuum failed: {e}")

    def run_reindex(self):
        if not self.db: return
        try:
            self.db.maintenance_reindex()
            QMessageBox.information(self, "Success", "Database reindex completed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Reindex failed: {e}")

    def _refresh_all_group_combos(self):
        if not self.db:
            return
        try:
            group_list = self.db.get_all_groups()

            self.new_subgroup_parent_combo.clear()
            self.new_subgroup_parent_combo.addItems([""] + group_list)

            self.existing_subgroups_filter_combo.clear()
            self.existing_subgroups_filter_combo.addItems([""] + group_list)

            if self.search_tab_ref and hasattr(self.search_tab_ref, "group_combo"):
                self.search_tab_ref.group_combo.clear()
                self.search_tab_ref.group_combo.addItems([""] + group_list)
                self.search_tab_ref.group_combo.setCurrentIndex(0)

        except Exception as e:
            print(f"Error refreshing group combos: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to refresh group dropdowns:\n{str(e)}"
            )

    def refresh_subgroup_autocomplete(self):
        if not self.db:
            return
        if not self.search_tab_ref or not hasattr(
            self.search_tab_ref, "subgroup_combo"
        ):
            return
        try:
            subgroup_list = self.db.get_all_subgroups()
            self.search_tab_ref.subgroup_combo.clear()
            self.search_tab_ref.subgroup_combo.addItems([""] + subgroup_list)
            self.search_tab_ref.subgroup_combo.setCurrentIndex(0)
        except Exception as e:
            print(f"Error refreshing subgroup autocomplete data: {e}")

    def update_button_states(self, connected: bool):
        self.btn_connect.setVisible(not connected)
        self.btn_disconnect.setVisible(connected)
        self.btn_reset_db.setVisible(connected)
        self.btn_vacuum.setVisible(connected)
        self.btn_reindex.setVisible(connected)

        self.db_host.setEnabled(not connected)
        self.db_port.setEnabled(not connected)
        self.db_user.setEnabled(not connected)
        self.db_password.setEnabled(not connected)
        self.db_name.setEnabled(not connected)

        self.populate_group.setEnabled(connected)
        self.btn_auto_populate.setEnabled(connected)
        self.btn_import_tags.setEnabled(connected)

        self.btn_remove_group.setEnabled(connected)
        self.btn_remove_subgroup.setEnabled(connected)
        self.btn_remove_tag.setEnabled(connected)

        if self.scan_tab_ref:
            self.scan_tab_ref.update_button_states(connected)

        if self.search_tab_ref:
            self.search_tab_ref.update_search_button_state(connected)

    # --- New Bulk Tag Import Methods ---

    def browse_json_file(self):
        """Opens a file dialog to select a JSON file."""
        initial_dir = Path(os.getcwd())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select JSON Tags File",
            str(initial_dir),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if file_path:
            self.json_file_path_edit.setText(file_path)

    def import_tags_from_json(self):
        """Reads the selected JSON file and imports tags into the database."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        file_path = self.json_file_path_edit.text().strip()
        tag_type = self.bulk_tag_type_combo.currentText().strip().title()

        if not file_path or not Path(file_path).is_file():
            QMessageBox.warning(self, "Error", "Please select a valid JSON file.")
            return

        imported_tags = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if (
                isinstance(data, dict)
                and "tags" in data
                and isinstance(data["tags"], list)
            ):
                tag_list = data["tags"]
            elif isinstance(data, list):
                # Allow a direct array of strings as a fallback
                tag_list = [item for item in data if isinstance(item, str)]
            else:
                QMessageBox.critical(
                    self,
                    "JSON Format Error",
                    "JSON file must be an object with a 'tags' key containing a list of strings, "
                    "or a direct list of strings.",
                )
                return

            if not tag_list:
                QMessageBox.information(
                    self, "Import Info", "No valid tags found in the JSON file."
                )
                return

            progress = QProgressDialog(
                "Importing tags...", "Cancel", 0, len(tag_list), self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            for i, tag_name_raw in enumerate(tag_list):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                progress.setLabelText(
                    f"Importing tag {i + 1}/{len(tag_list)}: {tag_name_raw[:40]}..."
                )

                tag_name = str(tag_name_raw).strip()
                if tag_name:
                    self.db.add_tag(tag_name, tag_type if tag_type else None)
                    imported_tags += 1

            progress.close()

            # Final refresh and update
            self.refresh_tags_list()
            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()
            self.update_statistics()

            QMessageBox.information(
                self,
                "Import Success",
                f"Successfully imported and updated {imported_tags} tags with type '{tag_type if tag_type else 'None'}'.",
            )

        except json.JSONDecodeError:
            QMessageBox.critical(
                self, "File Error", "The selected file is not a valid JSON file."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"An error occurred during tag import:\n{str(e)}",
            )
        finally:
            if "progress" in locals() and progress.isVisible():
                progress.close()

    # --- Tag and Group Management Methods ---

    def create_new_group(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        group_names_str = self.new_group_name_edit.text().strip()
        group_names = [
            name.strip() for name in group_names_str.split(",") if name.strip()
        ]
        if not group_names:
            QMessageBox.warning(self, "Error", "Group Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in group_names:
                self.db.add_group(name)
                count += 1
            QMessageBox.information(
                self, "Success", f"Successfully created {count} group(s)."
            )
            self.new_group_name_edit.clear()
            self.refresh_groups_list()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create groups:\n{str(e)}")

    def create_new_subgroup(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        parent_group = self.new_subgroup_parent_combo.currentText().strip()
        if not parent_group:
            QMessageBox.warning(
                self, "Error", "You must select or enter a Parent Group."
            )
            return
        subgroup_names_str = self.new_subgroup_name_edit.text().strip()
        subgroup_names = [
            name.strip() for name in subgroup_names_str.split(",") if name.strip()
        ]
        if not subgroup_names:
            QMessageBox.warning(self, "Error", "Subgroup Name(s) cannot be empty.")
            return
        try:
            self.db.add_group(parent_group)
            count = 0
            for name in subgroup_names:
                self.db.add_subgroup(name, parent_group)
                count += 1
            QMessageBox.information(
                self,
                "Success",
                f"Successfully created {count} subgroup(s) for '{parent_group}'.",
            )
            self.new_subgroup_name_edit.clear()
            self._refresh_all_group_combos()
            self.new_subgroup_parent_combo.setCurrentText(parent_group)
            if self.existing_subgroups_filter_combo.currentText() == parent_group:
                self.refresh_subgroups_list()
            self.refresh_subgroup_autocomplete()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create subgroups:\n{str(e)}"
            )

    def create_new_tag(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        tag_names_str = self.new_tag_name_edit.text().strip()
        tag_type = self.new_tag_type_combo.currentText().strip().title()
        tag_names = [name.strip() for name in tag_names_str.split(",") if name.strip()]
        if not tag_names:
            QMessageBox.warning(self, "Error", "Tag Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in tag_names:
                self.db.add_tag(name, tag_type if tag_type else None)
                count += 1
            QMessageBox.information(
                self, "Success", f"Successfully created/updated {count} tag(s)."
            )
            self.new_tag_name_edit.clear()
            self.new_tag_type_combo.setCurrentIndex(0)
            self.refresh_tags_list()
            self.update_statistics()
            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tags:\n{str(e)}")

    def remove_selected_group(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.groups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a group from the list to remove."
            )
            return
        item = self.groups_table.item(current_row, 0)
        group_name = item.text()
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the group '{group_name}'?\n\n"
            f"WARNING: This will also delete ALL associated subgroups.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_group(group_name)
                self.refresh_groups_list()
                self.refresh_subgroups_list()
                self.refresh_subgroup_autocomplete()
                self.update_statistics()
                QMessageBox.information(
                    self, "Success", f"Group '{group_name}' and its subgroups removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to remove group:\n{str(e)}"
                )

    def remove_selected_subgroup(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.subgroups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a subgroup from the list to remove."
            )
            return
        item_subgroup = self.subgroups_table.item(current_row, 0)
        item_group = self.subgroups_table.item(current_row, 1)
        subgroup_name = item_subgroup.text()
        group_name = item_group.text()
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the subgroup '{subgroup_name}' from group '{group_name}'?\n\n"
            f"(Note: This only removes the subgroup from this list. Images already using this name will not be affected.)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_subgroup(subgroup_name, group_name)
                self.refresh_subgroups_list()
                self.refresh_subgroup_autocomplete()
                self.update_statistics()
                QMessageBox.information(
                    self, "Success", f"Subgroup '{subgroup_name}' removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to remove subgroup:\n{str(e)}"
                )

    def remove_selected_tag(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a tag from the list to remove."
            )
            return
        item = self.tags_table.item(current_row, 0)
        tag_name = item.text()
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the tag '{tag_name}'?\n\n"
            f"WARNING: This will also remove this tag from ALL images that use it.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_tag(tag_name)
                self.refresh_tags_list()
                self.update_statistics()
                if self.scan_tab_ref:
                    self.scan_tab_ref._setup_tag_checkboxes()
                QMessageBox.information(self, "Success", f"Tag '{tag_name}' removed.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove tag:\n{str(e)}")

    def refresh_groups_list(self):
        if not self.db:
            self.groups_table.setRowCount(0)
            return
        try:
            groups = self.db.get_all_groups()
            self.groups_table.setRowCount(len(groups))
            for row, group_name in enumerate(groups):
                name_item = QTableWidgetItem(group_name)
                self.groups_table.setItem(row, 0, name_item)
            self._refresh_all_group_combos()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load groups list:\n{str(e)}"
            )

    def refresh_subgroups_list(self):
        if not self.db:
            self.subgroups_table.setRowCount(0)
            return

        parent_group_filter = self.existing_subgroups_filter_combo.currentText()

        results = []
        try:
            if not parent_group_filter:
                # CASE 1: No filter selected -> Show ALL subgroups with their parents
                #
                raw_data = self.db.get_all_subgroups_detailed()
                results = raw_data  # List of (subgroup_name, group_name)
            else:
                # CASE 2: Filter selected -> Show only specific subgroups
                #
                subgroup_names = self.db.get_subgroups_for_group(parent_group_filter)
                # format as list of tuples to match Case 1
                results = [(name, parent_group_filter) for name in subgroup_names]

            # Populate the Table
            self.subgroups_table.setRowCount(len(results))
            for row, (sub_name, grp_name) in enumerate(results):
                name_item = QTableWidgetItem(sub_name)
                group_item = QTableWidgetItem(grp_name)

                # Lock the parent group cell so it can't be edited here (only subgroup name is editable)
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.subgroups_table.setItem(row, 0, name_item)
                self.subgroups_table.setItem(row, 1, group_item)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load subgroups list:\n{str(e)}"
            )

    def refresh_tags_list(self):
        if not self.db:
            self.tags_table.setRowCount(0)
            return
        try:
            tags = self.db.get_all_tags_with_types()
            self.tags_table.setRowCount(len(tags))
            for row, tag_data in enumerate(tags):
                name_item = QTableWidgetItem(tag_data["name"])
                type_item = QTableWidgetItem(tag_data["type"])
                self.tags_table.setItem(row, 0, name_item)
                self.tags_table.setItem(row, 1, type_item)
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tags list:\n{str(e)}")

    def store_old_value(self, row, col):
        table = self.sender()
        if not table:
            return
        item = table.item(row, col)
        if item:
            self.old_edit_value = item.text()

    def handle_group_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        new_name = item.text().strip()
        old_name = self.old_edit_value
        self.old_edit_value = None
        if not new_name:
            QMessageBox.warning(self, "Error", "Group name cannot be empty.")
            item.setText(old_name)
            return
        if new_name == old_name:
            return
        try:
            self.db.rename_group(old_name, new_name)
            self.refresh_groups_list()
            self.refresh_subgroups_list()
            self.update_statistics()
        except psycopg2.errors.UniqueViolation:
            QMessageBox.warning(
                self, "Error", f"A group named '{new_name}' already exists."
            )
            item.setText(old_name)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename group:\n{str(e)}")
            item.setText(old_name)

    def handle_subgroup_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        col = item.column()
        if col != 0:
            if item.text() != self.old_edit_value:
                item.setText(self.old_edit_value)
            self.old_edit_value = None
            return
        new_name = item.text().strip()
        old_name = self.old_edit_value
        self.old_edit_value = None
        if new_name == old_name:
            return
        row = item.row()
        parent_group = self.subgroups_table.item(row, 1).text()
        if not new_name:
            QMessageBox.warning(self, "Error", "Subgroup name cannot be empty.")
            item.setText(old_name)
            return
        try:
            self.db.rename_subgroup(old_name, new_name, parent_group)
            self.refresh_subgroup_autocomplete()
            self.update_statistics()
        except psycopg2.errors.UniqueViolation:
            QMessageBox.warning(
                self,
                "Error",
                f"A subgroup named '{new_name}' already exists in this group.",
            )
            item.setText(old_name)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename subgroup:\n{str(e)}")
            item.setText(old_name)

    def handle_tag_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        new_value = item.text().strip()
        old_value = self.old_edit_value
        self.old_edit_value = None
        if new_value == old_value:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            old_name = old_value
            new_name = new_value
            if not new_name:
                QMessageBox.warning(self, "Error", "Tag name cannot be empty.")
                item.setText(old_name)
                return
            try:
                self.db.rename_tag(old_name, new_name)
                if item.text() != new_name:
                    item.setText(new_name)
                self.update_statistics()
                if self.scan_tab_ref:
                    self.scan_tab_ref._setup_tag_checkboxes()
            except psycopg2.errors.UniqueViolation:
                QMessageBox.warning(
                    self, "Error", f"A tag named '{new_name}' already exists."
                )
                item.setText(old_name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename tag:\n{str(e)}")
                item.setText(old_name)
        elif col == 1:
            tag_name = self.tags_table.item(row, 0).text()
            new_type = new_value.title()
            try:
                self.db.update_tag_type(tag_name, new_type)
                if item.text() != new_type:
                    item.setText(new_type)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to update tag type:\n{str(e)}"
                )
                item.setText(old_value)

    def show_group_context_menu(self, pos):
        item = self.groups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit Group")
        remove_action = menu.addAction("Remove Group")
        action = menu.exec(self.groups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_group_cell()
        elif action == remove_action:
            self.remove_selected_group()

    def edit_selected_group_cell(self):
        item = self.groups_table.currentItem()
        if item:
            self.groups_table.editItem(item)

    def show_subgroup_context_menu(self, pos):
        item = self.subgroups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        if item.column() == 0:
            edit_action = menu.addAction("Edit Subgroup")
        else:
            edit_action = None
        remove_action = menu.addAction("Remove Subgroup")
        action = menu.exec(self.subgroups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_subgroup_cell()
        elif action == remove_action:
            self.remove_selected_subgroup()

    def edit_selected_subgroup_cell(self):
        current_row = self.subgroups_table.currentRow()
        if current_row < 0:
            return
        item_to_edit = self.subgroups_table.item(current_row, 0)
        if item_to_edit:
            self.subgroups_table.editItem(item_to_edit)

    def show_tag_context_menu(self, pos):
        item = self.tags_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit Cell")
        remove_action = menu.addAction("Remove Tag")
        action = menu.exec(self.tags_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_tag_cell()
        elif action == remove_action:
            self.remove_selected_tag()

    def edit_selected_tag_cell(self):
        item = self.tags_table.currentItem()
        if item:
            self.tags_table.editItem(item)

    def collect(self) -> dict:
        out = {
            "db_host": self.db_host.text().strip() or None,
            "db_port": self.db_port.text().strip() or None,
            "db_user": self.db_user.text().strip() or None,
            "db_password": self.db_password.text()
            or None,  # Included password for saving
            "db_name": self.db_name.text().strip() or None,
        }
        return out

    def get_default_config(self) -> dict:
        return {
            "db_host": "localhost",
            "db_port": "5432",
            "db_user": "postgres",
            "db_name": "imagedb",
            "db_password": "",
        }

    def set_config(self, config: dict):
        try:
            self.db_host.setText(config.get("db_host", "localhost"))
            self.db_port.setText(config.get("db_port", "5432"))
            self.db_user.setText(config.get("db_user", "postgres"))
            self.db_name.setText(config.get("db_name", "imagedb"))

            # Restore password if present
            if "db_password" in config:
                self.db_password.setText(config.get("db_password", ""))

            self.connect_database()
        except Exception as e:
            print(f"Error applying DatabaseTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

    def auto_populate_from_source(self):
        """
        Scans LOCAL_SOURCE_PATH.
        Level 1 Directories -> Groups
        Level 2 Directories -> Subgroups for that Group
        """
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        # Resolve to absolute path to avoid ambiguity
        source_path = Path(LOCAL_SOURCE_PATH).resolve()

        if not source_path.exists():
            QMessageBox.critical(
                self, "Path Error", f"The source path does not exist:\n{source_path}"
            )
            return

        # Simple confirmation
        confirm = QMessageBox.question(
            self,
            "Confirm Sync",
            f"This will scan the following directory:\n\n{source_path}\n\n"
            "Top-level folders will be added as Groups.\n"
            "Folders inside those will be added as Subgroups.\n"
            "Existing entries will be skipped.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.No:
            return

        # Progress Dialog
        progress = QProgressDialog("Scanning directories...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        groups_added = 0
        subgroups_added = 0
        errors = []

        try:
            # Iterate Level 1 (Groups)
            for group_dir in source_path.iterdir():
                if progress.wasCanceled():
                    break

                if group_dir.is_dir() and not group_dir.name.startswith("."):
                    group_name = group_dir.name.strip()
                    if not group_name:
                        continue

                    try:
                        # Add Group to DB (ImageDatabase handles "ON CONFLICT DO NOTHING")
                        self.db.add_group(group_name)
                        groups_added += 1

                        # Iterate Level 2 (Subgroups)
                        for subgroup_dir in group_dir.iterdir():
                            if (
                                subgroup_dir.is_dir()
                                and not subgroup_dir.name.startswith(".")
                            ):
                                subgroup_name = subgroup_dir.name.strip()
                                if not subgroup_name:
                                    continue

                                try:
                                    # Add Subgroup to DB
                                    self.db.add_subgroup(subgroup_name, group_name)
                                    subgroups_added += 1
                                except Exception as e_sub:
                                    print(
                                        f"Error adding subgroup {subgroup_name}: {e_sub}"
                                    )
                                    # Don't stop the whole process for one subgroup error
                                    pass

                    except Exception as e_group:
                        errors.append(f"Group '{group_name}': {str(e_group)}")

            progress.close()

            # Refresh UIs
            self.refresh_groups_list()
            self._refresh_all_group_combos()
            self.refresh_subgroup_autocomplete()
            self.refresh_subgroups_list()
            self.update_statistics()

            msg = (
                f"Scan Finished.\n\n"
                f"Processed Groups: {groups_added}\n"
                f"Processed Subgroups: {subgroups_added}\n\n"
                f"(Note: Numbers indicate processed folders, duplicates were skipped)."
            )

            if errors:
                msg += "\n\nErrors encountered:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += "\n..."

            QMessageBox.information(self, "Sync Complete", msg)

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self, "Sync Error", f"An error occurred during scanning:\n{str(e)}"
            )
