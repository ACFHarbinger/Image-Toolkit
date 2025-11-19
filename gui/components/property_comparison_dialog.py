import os

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView,
    QDialog, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class PropertyComparisonDialog(QDialog):
    def __init__(self, property_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Property Comparison")
        self.setMinimumSize(600, 600) # Increased height slightly for vertical scrolling
        self.layout = QVBoxLayout(self)
        
        self.property_data = property_data
        self.table = self._create_table(property_data)
        
        self.layout.addWidget(self.table)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        self.layout.addWidget(close_button)

    def _create_table(self, data: List[Dict[str, Any]]) -> QTableWidget:
        if not data:
            table = QTableWidget(0, 1)
            table.setHorizontalHeaderLabels(["No Images Selected"])
            return table

        # 1. Determine which properties to display
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        # Define priority order
        # Note: "File Name" is removed from here because it will be used as a column identifier
        priority_order = ["File Size", "Width", "Height", "Format", "Mode", "Last Modified", "Created", "Path", "Error"]
        
        # Create final list of keys (sections) to iterate through
        # We filter out 'File Name' from the keys list because it serves as the image identifier
        section_keys = [k for k in priority_order if k in all_keys]
        
        # Add any remaining keys that weren't in the priority list (excluding File Name)
        for k in sorted(list(all_keys)):
            if k not in section_keys and k != "File Name":
                section_keys.append(k)

        # 2. Calculate Dimensions
        # Rows = Number of Properties * Number of Images
        num_rows = len(section_keys) * len(data)
        num_cols = 3  # Columns: [Property Name, Image Name, Value]

        table = QTableWidget(num_rows, num_cols)
        table.setHorizontalHeaderLabels(["Property", "Image File", "Value"])
        
        # Hide vertical header (indices) as they aren't useful here
        table.verticalHeader().setVisible(False)

        # 3. Populate Table
        current_row = 0
        
        # Colors for visual section separation
        section_color_1 = QColor("#2c2f33") # Dark Gray (or standard background)
        section_color_2 = QColor("#23272a") # Slightly Darker Gray
        
        for i, key in enumerate(section_keys):
            # Alternate background color for every property section
            bg_color = section_color_1 if i % 2 == 0 else section_color_2
            
            for item in data:
                # Get Image Name (Identifier)
                img_name = item.get("File Name", os.path.basename(item.get("Path", "Unknown Image")))
                
                # Get Value
                val = str(item.get(key, 'N/A'))

                # Col 0: Property Name
                item_prop = QTableWidgetItem(key)
                item_prop.setBackground(bg_color)
                item_prop.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                # Col 1: Image Name
                item_name = QTableWidgetItem(img_name)
                item_name.setBackground(bg_color)
                item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                # Col 2: Value
                item_val = QTableWidgetItem(val)
                item_val.setBackground(bg_color)
                item_val.setTextAlignment(Qt.AlignCenter)
                
                table.setItem(current_row, 0, item_prop)
                table.setItem(current_row, 1, item_name)
                table.setItem(current_row, 2, item_val)
                
                current_row += 1

        # 4. Styling
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Property
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)      # Image Name (User can resize)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)          # Value (Fills rest)
        
        # Set a reasonable width for the middle column
        table.setColumnWidth(1, 200)
        
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        return table
