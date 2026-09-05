"""Module runtime contracts; legacy registry remains during shell migration."""

from .catalog import ModuleCatalog, PageDescriptor, RouteDescriptor, WorkspaceDescriptor
from .context import ModuleContext, ModuleServices
from .descriptor import ModuleCategory, ModuleDescriptor
from .events import (
    DatabaseAvailabilityChanged,
    EventHub,
    Fact,
    FilterByTagIntent,
    GroupCatalogChanged,
    ImportPathsIntent,
    Intent,
    NavigateIntent,
    SubgroupCatalogChanged,
    TagCatalogChanged,
)
from .legacy_bridge import LegacyNavigationBridge
from .library_service import LIBRARY_DATABASE_SERVICE, LibraryDatabaseService
from .registry import ModuleRegistry
from .runtime import ModuleHandle, ModuleRuntime, WidgetHandle

__all__ = [
    "DatabaseAvailabilityChanged",
    "EventHub",
    "Fact",
    "FilterByTagIntent",
    "GroupCatalogChanged",
    "ImportPathsIntent",
    "Intent",
    "LegacyNavigationBridge",
    "LIBRARY_DATABASE_SERVICE",
    "LibraryDatabaseService",
    "ModuleCatalog",
    "ModuleCategory",
    "ModuleContext",
    "ModuleDescriptor",
    "ModuleHandle",
    "ModuleRegistry",
    "ModuleRuntime",
    "ModuleServices",
    "NavigateIntent",
    "PageDescriptor",
    "RouteDescriptor",
    "SubgroupCatalogChanged",
    "TagCatalogChanged",
    "WidgetHandle",
    "WorkspaceDescriptor",
]
