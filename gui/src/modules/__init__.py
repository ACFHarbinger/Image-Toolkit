"""Module runtime contracts; legacy registry remains during shell migration."""

from .catalog import ModuleCatalog, PageDescriptor, RouteDescriptor, WorkspaceDescriptor
from .context import ModuleContext, ModuleServices
from .descriptor import ModuleCategory, ModuleDescriptor
from .events import EventHub, Fact, Intent, NavigateIntent
from .legacy_bridge import LegacyNavigationBridge
from .registry import ModuleRegistry
from .runtime import ModuleHandle, ModuleRuntime, WidgetHandle

__all__ = [
    "EventHub",
    "Fact",
    "Intent",
    "LegacyNavigationBridge",
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
    "WidgetHandle",
    "WorkspaceDescriptor",
]
