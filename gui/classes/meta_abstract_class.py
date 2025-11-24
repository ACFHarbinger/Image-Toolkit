from abc import ABCMeta, abstractmethod
from PySide6.QtCore import QObject


class MetaAbstractClass(ABCMeta, type(QObject)):
    """A metaclass combining ABCMeta and Qt's metaclass"""
    
    @abstractmethod
    def get_default_config(self) -> dict:
        """Get default configuration."""
        pass

    @abstractmethod
    def set_config(self, config: dict):
        """Set input field values from selected configuration."""
        pass

    @staticmethod
    def join_list_str(text):
        """Convert a comma/space separated string to list of strings, stripping whitespace."""
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
