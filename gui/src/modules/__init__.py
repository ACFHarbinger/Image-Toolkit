"""gui/src/modules/__init__.py
============================
ModuleDescriptor + ModuleHost architecture contract (§1.3, #527).
"""

from __future__ import annotations

from .descriptor import (
    ConstructionPolicy,
    ModuleCategory,
    ModuleDescriptor,
    ModuleRoute,
)
from .host import ModuleHostWidget
from .pilots import create_log_panel_descriptor
from .registry import ModuleRegistry

__all__ = [
    "ConstructionPolicy",
    "ModuleCategory",
    "ModuleDescriptor",
    "ModuleHostWidget",
    "ModuleRegistry",
    "ModuleRoute",
    "create_log_panel_descriptor",
]
