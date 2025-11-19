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
    """
    Dialog to compare image properties in a vertical, sectioned layout.
    """
    def __init__(self, property_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Property Comparison")
        self.setMinimumSize(600, 600)
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

        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        # Define priority order for properties
        priority_order = [
            "File Size", "Width", "Height", "Format", 
            "Mode", "Last Modified", "Created", "Path", "Error"
        ]
        
        section_keys = [k for k in priority_order if k in all_keys]
        
        for k in sorted(list(all_keys)):
            if k not in section_keys and k != "File Name":
                section_keys.append(k)

        num_rows = len(section_keys) * len(data)
        num_cols = 3 

        table = QTableWidget(num_rows, num_cols)
        table.setHorizontalHeaderLabels(["Property", "Image File", "Value"])
        table.verticalHeader().setVisible(False)

        current_row = 0
        section_color_1 = QColor("#2c2f33") 
        section_color_2 = QColor("#23272a") 
        
        for i, key in enumerate(section_keys):
            bg_color = section_color_1 if i % 2 == 0 else section_color_2
            
            for item in data:
                img_name = item.get("File Name", os.path.basename(item.get("Path", "Unknown Image")))
                val = str(item.get(key, 'N/A'))

                item_prop = QTableWidgetItem(key)
                item_prop.setBackground(bg_color)
                item_prop.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                item_name = QTableWidgetItem(img_name)
                item_name.setBackground(bg_color)
                item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                item_val = QTableWidgetItem(val)
                item_val.setBackground(bg_color)
                item_val.setTextAlignment(Qt.AlignCenter)
                
                table.setItem(current_row, 0, item_prop)
                table.setItem(current_row, 1, item_name)
                table.setItem(current_row, 2, item_val)
                
                current_row += 1

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)     
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)       
        table.setColumnWidth(1, 200)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        return table
