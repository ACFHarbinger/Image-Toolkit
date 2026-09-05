"""Declarative modules and navigation registry (§2.36)."""

from .descriptor import ModuleCategory, ModuleDescriptor
from .registry import ModuleRegistry

__all__ = ["ModuleCategory", "ModuleDescriptor", "ModuleRegistry"]
