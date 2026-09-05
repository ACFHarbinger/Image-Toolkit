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
from .stitch_workspace import (
    STITCH_ROUTES,
    STITCH_WORKSPACE_FLAG,
    STITCH_WORKSPACE_ID,
    StitchWorkspaceHandle,
    register_stitch_workspace,
    stitch_workspace_enabled,
)

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
    "STITCH_ROUTES",
    "STITCH_WORKSPACE_FLAG",
    "STITCH_WORKSPACE_ID",
    "StitchWorkspaceHandle",
    "SubgroupCatalogChanged",
    "TagCatalogChanged",
    "WidgetHandle",
    "WorkspaceDescriptor",
    "register_stitch_workspace",
    "stitch_workspace_enabled",
]
