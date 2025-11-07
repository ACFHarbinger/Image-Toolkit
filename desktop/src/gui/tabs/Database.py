import os
import psycopg2 # Import for error handling
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QScrollArea, QGroupBox,
    QMessageBox, QComboBox,
    QAbstractItemView, QMenu,
    QFormLayout, QHBoxLayout, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QHeaderView,
    QTableWidget, QTableWidgetItem, QSizePolicy,
)
from .BaseTab import BaseTab 
from ... import PgvectorImageDatabase as ImageDatabase
from ..styles import apply_shadow_effect
from dotenv import load_dotenv


class DatabaseTab(BaseTab):
    """
    Manages PostgreSQL connection, statistics display, and tag/group population.
    """
    def __init__(self, dropdown=True, env_path='env/vars.env'):
        super().__init__()
        self.dropdown = dropdown
        self.db: Optional[ImageDatabase] = None
        self.scan_tab_ref = None 
        self.search_tab_ref = None 
        self.old_edit_value = None # Store the value of a cell before editing
        
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
        self.db_name = QLineEdit(os.getenv("DB_NAME"),)
        
        conn_form_layout.addRow("Host:", self.db_host)
        conn_form_layout.addRow("Port:", self.db_port)
        conn_form_layout.addRow("User:", self.db_user)
        conn_form_layout.addRow("Password:", self.db_password)
        conn_form_layout.addRow("Database Name:", self.db_name)
        
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.addLayout(conn_form_layout)
        
        self.button_conn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect to PostgreSQL")
        self.btn_connect.setStyleSheet("background-color: #3498db; color: white; padding: 10px;")
        apply_shadow_effect(self.btn_connect, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_connect.clicked.connect(self.connect_database)
        self.button_conn_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("Disconnect from PostgreSQL")
        self.btn_disconnect.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px;")
        apply_shadow_effect(self.btn_disconnect, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_disconnect.clicked.connect(self.disconnect_database)
        self.btn_disconnect.hide()
        self.button_conn_layout.addWidget(self.btn_disconnect)

        conn_layout.addLayout(self.button_conn_layout)
        main_layout.addWidget(conn_group)
        
        # Statistics display
        self.stats_label = QLabel("Not connected to database")
        self.stats_label.setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;")
        main_layout.addWidget(self.stats_label)
        
        # --- Populate Database Section ---
        self.populate_group = QGroupBox("Populate Database")
        populate_layout = QVBoxLayout(self.populate_group)
        
        # --- Create New Group section ---
        create_group_group = QGroupBox("Create Group(s)")
        create_group_layout = QFormLayout(create_group_group)
        
        self.new_group_name_edit = QLineEdit()
        self.new_group_name_edit.setPlaceholderText("group1, group2, group3 ... (comma-separated)")
        create_group_layout.addRow("Group Name(s):", self.new_group_name_edit)
        
        self.btn_create_group = QPushButton("Create Group(s)")
        apply_shadow_effect(self.btn_create_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_create_group.clicked.connect(self.create_new_group)
        create_group_layout.addRow(self.btn_create_group)
        
        # --- NEW: Connect Enter key to button click ---
        self.new_group_name_edit.returnPressed.connect(self.btn_create_group.click)
        
        populate_layout.addWidget(create_group_group)

        # --- Existing Groups section ---
        existing_groups_group = QGroupBox("Existing Groups")
        existing_groups_layout = QVBoxLayout(existing_groups_group)
        
        groups_btn_layout = QHBoxLayout()
        self.btn_refresh_groups = QPushButton("Refresh List")
        apply_shadow_effect(self.btn_refresh_groups, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_refresh_groups.clicked.connect(self.refresh_groups_list)
        groups_btn_layout.addWidget(self.btn_refresh_groups)
        
        self.btn_remove_group = QPushButton("Remove Selected Group")
        self.btn_remove_group.setStyleSheet("background-color: #e74c3c; color: white;")
        apply_shadow_effect(self.btn_remove_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_remove_group.clicked.connect(self.remove_selected_group)
        groups_btn_layout.addWidget(self.btn_remove_group)
        existing_groups_layout.addLayout(groups_btn_layout)

        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(1)
        self.groups_table.setHorizontalHeaderLabels(["Group Name"])
        self.groups_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.groups_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.groups_table.setStyleSheet("""
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
        """)
        self.groups_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.groups_table.setMinimumHeight(200) 
        
        self.groups_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.groups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups_table.customContextMenuRequested.connect(self.show_group_context_menu)
        self.groups_table.cellPressed.connect(self.store_old_value)
        self.groups_table.itemChanged.connect(self.handle_group_edited)
        
        existing_groups_layout.addWidget(self.groups_table)
        populate_layout.addWidget(existing_groups_group)

        # Create New Tag section
        create_tag_group = QGroupBox("Create/Update Tag(s)")
        create_tag_layout = QFormLayout(create_tag_group)
        
        self.new_tag_name_edit = QLineEdit()
        self.new_tag_name_edit.setPlaceholderText("tag1, tag2, tag3 ... (comma-separated)")
        create_tag_layout.addRow("Tag Name(s):", self.new_tag_name_edit)
        
        self.new_tag_type_combo = QComboBox()
        self.new_tag_type_combo.setEditable(True)
        self.new_tag_type_combo.addItems(["", "Artist", "Series", "Character", "General", "Meta"])
        self.new_tag_type_combo.setPlaceholderText("e.g., Artist, Character, General (Optional)")
        create_tag_layout.addRow("Tag Type (applies to all):", self.new_tag_type_combo)
        
        self.btn_create_tag = QPushButton("Create/Update Tag(s)")
        apply_shadow_effect(self.btn_create_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_create_tag.clicked.connect(self.create_new_tag)
        create_tag_layout.addRow(self.btn_create_tag)
        
        # --- NEW: Connect Enter key to button click ---
        self.new_tag_name_edit.returnPressed.connect(self.btn_create_tag.click)
        self.new_tag_type_combo.lineEdit().returnPressed.connect(self.btn_create_tag.click)
        
        populate_layout.addWidget(create_tag_group)

        # Existing Tags section
        existing_tags_group = QGroupBox("Existing Tags")
        existing_tags_layout = QVBoxLayout(existing_tags_group)
        
        tags_btn_layout = QHBoxLayout()
        self.btn_refresh_tags = QPushButton("Refresh List")
        apply_shadow_effect(self.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_refresh_tags.clicked.connect(self.refresh_tags_list)
        tags_btn_layout.addWidget(self.btn_refresh_tags)
        
        self.btn_remove_tag = QPushButton("Remove Selected Tag")
        self.btn_remove_tag.setStyleSheet("background-color: #e74c3c; color: white;")
        apply_shadow_effect(self.btn_remove_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_remove_tag.clicked.connect(self.remove_selected_tag)
        tags_btn_layout.addWidget(self.btn_remove_tag)
        existing_tags_layout.addLayout(tags_btn_layout)

        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(2)
        self.tags_table.setHorizontalHeaderLabels(["Tag Name", "Tag Type"])
        self.tags_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tags_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tags_table.setAlternatingRowColors(True)
        self.tags_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tags_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tags_table.setStyleSheet("""
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
        """)
        self.tags_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        """Connect to the PostgreSQL database using fields."""
        try:
            db_host = self.db_host.text().strip()
            db_port = self.db_port.text().strip()
            db_user = self.db_user.text().strip()
            db_password = self.db_password.text() 
            db_name = self.db_name.text().strip()
            if not all([db_host, db_port, db_user, db_name]):
                QMessageBox.warning(self, "Error", "All connection fields are required.")
                return
            
            if self.db: self.db.close()
            
            self.db = ImageDatabase(
                db_name=db_name, db_user=db_user, db_password=db_password, 
                db_host=db_host, db_port=db_port,
                embed_dim=128 
            )
            self.update_statistics()
            self.update_button_states(connected=True)
            self.refresh_group_autocomplete() 
            self.refresh_tags_list()
            self.refresh_groups_list() 
            
            QMessageBox.information(self, "Success", f"Connected to PostgreSQL DB: {db_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to database:\n{str(e)}")
            self.update_button_states(connected=False)
            self.stats_label.setText("Connection Failed")
            self.stats_label.setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;")

    def disconnect_database(self):
        """Disconnects from the PostgreSQL database."""
        if not self.db:
            return
        
        try:
            self.db.close()
            self.db = None
            self.update_button_states(connected=False)
            
            self.stats_label.setText("Not connected to database")
            self.stats_label.setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;")
            
            self.tags_table.setRowCount(0)
            self.groups_table.setRowCount(0) 
            if self.search_tab_ref and hasattr(self.search_tab_ref, 'group_combo'):
                self.search_tab_ref.group_combo.clear()
            
            QMessageBox.information(self, "Disconnected", "Successfully disconnected from the database.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error during disconnection:\n{str(e)}")
    
    def update_statistics(self):
        """Update database statistics display"""
        if not self.db: return
        try:
            stats = self.db.get_statistics()
            stats_text = (
                f"📊 Database Statistics:\n"
                f"Images: {stats.get('total_images', 0)} | "
                f"Tags: {stats.get('total_tags', 0)} | "
                f"Groups: {stats.get('total_groups', 0)}"
            )
            self.stats_label.setText(stats_text)
            self.stats_label.setStyleSheet("padding: 10px; background-color: #27ae60; color: white; border-radius: 5px; font-weight: bold;")
        except Exception as e:
            self.stats_label.setText(f"Error getting statistics: {str(e)}")
            self.stats_label.setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;")
    
    def refresh_group_autocomplete(self):
        """Refresh group autocomplete suggestions in the Search tab."""
        if not self.db: return
        
        if not self.search_tab_ref or not hasattr(self.search_tab_ref, 'group_combo'):
            print("Warning: SearchTab reference not set or 'group_combo' not found.")
            return
            
        try:
            group_list = self.db.get_all_groups()
            self.search_tab_ref.group_combo.clear()
            self.search_tab_ref.group_combo.addItems(group_list)
            self.search_tab_ref.group_combo.setCurrentIndex(-1)
        except Exception as e:
            print(f"Error refreshing group autocomplete data: {e}")

    def update_button_states(self, connected: bool):
        """Enable or disable buttons based on database connection status."""
        
        self.btn_connect.setVisible(not connected)
        self.btn_disconnect.setVisible(connected)
        
        self.db_host.setEnabled(not connected)
        self.db_port.setEnabled(not connected)
        self.db_user.setEnabled(not connected)
        self.db_password.setEnabled(not connected)
        self.db_name.setEnabled(not connected)

        self.populate_group.setEnabled(connected)
        
        self.btn_remove_group.setEnabled(connected)
        self.btn_remove_tag.setEnabled(connected)
        
        if self.scan_tab_ref:
             self.scan_tab_ref.update_button_states(connected)
             
    # --- Tag and Group Management Methods ---

    def create_new_group(self):
        """Creates new groups in the database from a comma-separated list."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
            
        group_names_str = self.new_group_name_edit.text().strip()
        group_names = [name.strip() for name in group_names_str.split(',') if name.strip()]
        
        if not group_names:
            QMessageBox.warning(self, "Error", "Group Name(s) cannot be empty.")
            return
        
        try:
            count = 0
            for name in group_names:
                self.db.add_group(name)
                count += 1
            
            QMessageBox.information(self, "Success", f"Successfully created {count} group(s).")
            self.new_group_name_edit.clear()
            self.refresh_groups_list() 
            self.refresh_group_autocomplete() 
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create groups:\n{str(e)}")

    def create_new_tag(self):
        """Creates new tags in the database from a comma-separated list."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
            
        tag_names_str = self.new_tag_name_edit.text().strip()
        tag_type = self.new_tag_type_combo.currentText().strip().title()
        
        tag_names = [name.strip() for name in tag_names_str.split(',') if name.strip()]
        
        if not tag_names:
            QMessageBox.warning(self, "Error", "Tag Name(s) cannot be empty.")
            return
        
        try:
            count = 0
            for name in tag_names:
                self.db.add_tag(name, tag_type if tag_type else None)
                count += 1
                
            QMessageBox.information(self, "Success", f"Successfully created/updated {count} tag(s).")
            self.new_tag_name_edit.clear()
            self.new_tag_type_combo.setCurrentIndex(0) 
            self.refresh_tags_list() 
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tags:\n{str(e)}")

    def remove_selected_group(self):
        """Removes the selected group from the 'groups' table."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        
        current_row = self.groups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select a group from the list to remove.")
            return
            
        item = self.groups_table.item(current_row, 0)
        group_name = item.text()
        
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the group '{group_name}'?\n\n"
            f"(Note: This only removes the group from this list. Images already using this group name will not be affected.)",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_group(group_name)
                self.refresh_groups_list()
                self.refresh_group_autocomplete()
                self.update_statistics()
                QMessageBox.information(self, "Success", f"Group '{group_name}' removed.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove group:\n{str(e)}")

    def remove_selected_tag(self):
        """Removes the selected tag from the 'tags' table."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select a tag from the list to remove.")
            return
            
        item = self.tags_table.item(current_row, 0)
        tag_name = item.text()

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the tag '{tag_name}'?\n\n"
            f"WARNING: This will also remove this tag from ALL images that use it.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_tag(tag_name)
                self.refresh_tags_list()
                self.update_statistics() 
                QMessageBox.information(self, "Success", f"Tag '{tag_name}' removed.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove tag:\n{str(e)}")

    def refresh_groups_list(self):
        """Fetches all groups from the DB and populates the table."""
        if not self.db:
            self.groups_table.setRowCount(0)
            return
            
        try:
            groups = self.db.get_all_groups() 
            self.groups_table.setRowCount(len(groups))
            
            for row, group_name in enumerate(groups):
                name_item = QTableWidgetItem(group_name)
                self.groups_table.setItem(row, 0, name_item)
            
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load groups list:\n{str(e)}")

    def refresh_tags_list(self):
        """Fetches all tags from the DB and populates the table."""
        if not self.db:
            self.tags_table.setRowCount(0)
            return
            
        try:
            tags = self.db.get_all_tags_with_types()
            self.tags_table.setRowCount(len(tags))
            
            for row, tag_data in enumerate(tags):
                name_item = QTableWidgetItem(tag_data['name'])
                type_item = QTableWidgetItem(tag_data['type'])
                
                self.tags_table.setItem(row, 0, name_item)
                self.tags_table.setItem(row, 1, type_item)
            
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tags list:\n{str(e)}")
            
    # --- Context Menu and Edit Handlers ---
    
    def store_old_value(self, row, col):
        """Stores the value of a cell *before* an edit begins."""
        table = self.sender()
        if not table:
            return
        item = table.item(row, col)
        if item:
            self.old_edit_value = item.text()

    def handle_group_edited(self, item: QTableWidgetItem):
        """Handles the renaming of a group after its cell is edited."""
        if not self.db or self.old_edit_value is None:
            return

        new_name = item.text().strip()
        old_name = self.old_edit_value
        self.old_edit_value = None # Reset old value

        if not new_name:
            QMessageBox.warning(self, "Error", "Group name cannot be empty.")
            item.setText(old_name) # Revert change
            return
        
        if new_name == old_name:
            return # No change

        try:
            self.db.rename_group(old_name, new_name)
            self.refresh_group_autocomplete()
            self.update_statistics()
        except psycopg2.errors.UniqueViolation:
            QMessageBox.warning(self, "Error", f"A group named '{new_name}' already exists.")
            item.setText(old_name) # Revert change
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename group:\n{str(e)}")
            item.setText(old_name) # Revert change
            
    def handle_tag_edited(self, item: QTableWidgetItem):
        """Handles the renaming of a tag or its type after its cell is edited."""
        if not self.db or self.old_edit_value is None:
            return

        new_value = item.text().strip()
        old_value = self.old_edit_value
        self.old_edit_value = None # Reset old value
        
        if new_value == old_value:
            return

        row = item.row()
        col = item.column()

        if col == 0: # Renaming the tag
            tag_name_item = self.tags_table.item(row, 0) # This is the item that was just edited
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
            except psycopg2.errors.UniqueViolation:
                QMessageBox.warning(self, "Error", f"A tag named '{new_name}' already exists.")
                item.setText(old_name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename tag:\n{str(e)}")
                item.setText(old_name)

        elif col == 1: # Updating the type
            tag_name_item = self.tags_table.item(row, 0)
            tag_name = tag_name_item.text()
            new_type = new_value.title() # Standardize to Title Case

            try:
                self.db.update_tag_type(tag_name, new_type)
                if item.text() != new_type:
                    item.setText(new_type)
                # No need to update stats here, as total tags doesn't change
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update tag type:\n{str(e)}")
                item.setText(old_value)

    def show_group_context_menu(self, pos):
        """Shows a right-click context menu for the groups table."""
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
        """Triggers the editor for the currently selected group cell."""
        item = self.groups_table.currentItem()
        if item:
            self.groups_table.editItem(item)

    def show_tag_context_menu(self, pos):
        """Shows a right-click context menu for the tags table."""
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
        """Triggers the editor for the currently selected tag cell."""
        item = self.tags_table.currentItem()
        if item:
            self.tags_table.editItem(item)
            
    def collect(self) -> dict:
        """Collect current inputs from the Database tab as a dict."""
        out = {
            "db_host": self.db_host.text().strip() or None,
            "db_port": self.db_port.text().strip() or None,
            "db_user": self.db_user.text().strip() or None,
            "db_name": self.db_name.text().strip() or None,
        }
        return out
