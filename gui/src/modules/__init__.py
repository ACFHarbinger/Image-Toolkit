"""gui/src/modules/__init__.py
============================
Module runtime contracts, catalog, and lifecycle management (§2.36, #527, #533).
"""

from __future__ import annotations

from .application_catalog import build_application_catalog
from .catalog import (
    CatalogDescriptor,
    ModuleCatalog,
    ModuleCategory,
    ModuleFactory,
    ModuleKind,
    PageDescriptor,
    RouteDescriptor,
    WorkspaceDescriptor,
)
from .context import ModuleContext, ModuleServices
from .descriptor import (
    ConstructionPolicy,
    ModuleDescriptor,
    ModuleRoute,
)
from .events import (
    DatabaseAvailabilityChanged,
    EventHub,
    EventSubscription,
    Fact,
    FilterByTagIntent,
    GroupCatalogChanged,
    ImportPathsIntent,
    InspectImageIntent,
    Intent,
    ModuleActivated,
    ModuleDeactivated,
    ModuleEvent,
    NavigateIntent,
    SelectionChangedFact,
    SubgroupCatalogChanged,
    TagCatalogChanged,
    TelemetryUpdatedFact,
    ToggleInspectorIntent,
)
from .host import ModuleHostWidget
from .legacy_bridge import LegacyNavigationBridge
from .library_service import (
    LIBRARY_DATABASE_SERVICE,
    LibraryDatabaseService,
    coerce_library_database_service,
)
from .pilots import create_log_panel_descriptor
from .registry import ModuleRegistry
from .runtime import ModuleHandle, ModuleRuntime, WidgetHandle
from .stitch_workspace import (
    STITCH_ROUTES,
    STITCH_WORKSPACE_FLAG,
    STITCH_WORKSPACE_ID,
    StitchWorkspaceHandle,
    create_stitch_workspace,
    register_stitch_workspace,
    stitch_workspace_enabled,
)

__all__ = [
    "CatalogDescriptor",
    "ConstructionPolicy",
    "DatabaseAvailabilityChanged",
    "EventHub",
    "EventSubscription",
    "Fact",
    "FilterByTagIntent",
    "GroupCatalogChanged",
    "ImportPathsIntent",
    "InspectImageIntent",
    "Intent",
    "LIBRARY_DATABASE_SERVICE",
    "LegacyNavigationBridge",
    "LibraryDatabaseService",
    "ModuleActivated",
    "ModuleCatalog",
    "ModuleCategory",
    "ModuleContext",
    "ModuleDeactivated",
    "ModuleDescriptor",
    "ModuleEvent",
    "ModuleFactory",
    "ModuleHandle",
    "ModuleHostWidget",
    "ModuleKind",
    "ModuleRegistry",
    "ModuleRoute",
    "ModuleRuntime",
    "ModuleServices",
    "NavigateIntent",
    "PageDescriptor",
    "RouteDescriptor",
    "SelectionChangedFact",
    "STITCH_ROUTES",
    "STITCH_WORKSPACE_FLAG",
    "STITCH_WORKSPACE_ID",
    "StitchWorkspaceHandle",
    "SubgroupCatalogChanged",
    "TagCatalogChanged",
    "TelemetryUpdatedFact",
    "ToggleInspectorIntent",
    "WidgetHandle",
    "WorkspaceDescriptor",
    "build_application_catalog",
    "coerce_library_database_service",
    "create_log_panel_descriptor",
    "create_stitch_workspace",
    "register_stitch_workspace",
    "stitch_workspace_enabled",
]
