from typing import List
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from abc import ABC, ABCMeta, abstractmethod


class MetaBaseTab(ABCMeta, type(QObject)):
    """A metaclass combining ABCMeta and Qt's metaclass"""
    pass


class BaseTab(QWidget, metaclass=MetaBaseTab):
    """Abstract base class for tabs with Qt + ABC compatibility"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def browse_files(self):
        pass

    @abstractmethod
    def browse_directory(self):
        pass

    @abstractmethod
    def browse_input(self):
        pass

    @abstractmethod
    def browse_output(self):
        pass

    def collect(self):
        pass

    @staticmethod
    def join_list_str(s: str) -> List[str]:
        """Convert a comma/space separated string to list of strings, stripping whitespace.
        Empty input returns [].
        """
        if not s:
            return []
        # Accept commas, spaces or semicolons as separators
        parts = [p.strip() for p in s.replace(";", ",").replace("  ", " ").replace(" ", ",").split(",")]
        return [p for p in parts if p]
