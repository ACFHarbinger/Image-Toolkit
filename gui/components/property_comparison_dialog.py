import os

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView,
    QDialog, QSizePolicy
)
from PySide6.QtCore import Qt


class PropertyComparisonDialog(QDialog):
    def __init__(self, property_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Property Comparison")
        self.setMinimumSize(800, 400)
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

        # Get all unique property keys (features)
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        
        # Define the order of keys for better readability
        key_order = ["File Name", "File Size", "Width", "Height", "Format", "Mode", "Last Modified", "Created", "Path", "Error"]
        final_keys = [k for k in key_order if k in all_keys] + sorted([k for k in all_keys if k not in key_order])
        
        num_rows = len(final_keys)
        num_cols = len(data)

        table = QTableWidget(num_rows, num_cols)
        
        # Set Row Headers (Properties)
        table.setVerticalHeaderLabels(final_keys)
        
        # Set Column Headers (File Names)
        column_headers = [os.path.basename(d.get("Path", f"File {i+1}")) for i, d in enumerate(data)]
        table.setHorizontalHeaderLabels(column_headers)

        # Populate the table
        for col_idx, item in enumerate(data):
            for row_idx, key in enumerate(final_keys):
                value = str(item.get(key, 'N/A'))
                table_item = QTableWidgetItem(value)
                
                # Align file names to the left, others centrally for comparison
                if key in ["Path", "File Name"]:
                    table_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    table_item.setTextAlignment(Qt.AlignCenter)
                    
                table.setItem(row_idx, col_idx, table_item)

        # Styling and resizing
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        return table
