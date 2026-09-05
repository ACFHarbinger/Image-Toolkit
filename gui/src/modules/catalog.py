"""gui/src/modules/catalog.py
==========================
Immutable module, workspace, and route metadata owned by one app (§2.36, #533).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

from .descriptor import ModuleCategory, ModuleDescriptor

if TYPE_CHECKING:
    from .context import ModuleContext
    from .runtime import ModuleHandle


ModuleFactory = Callable[["ModuleContext"], "ModuleHandle"]


class ModuleKind(str, Enum):
    PAGE = "page"
    WORKSPACE = "workspace"
    ROUTE = "route"


@dataclass(frozen=True, slots=True)
class PageDescriptor:
    """Descriptor for a standalone, lazily mounted page."""

    module_id: str
    title: str
    category: ModuleCategory
    factory: ModuleFactory
    icon_name: str = "box"
    search_terms: tuple[str, ...] = ()
    capability_flags: frozenset[str] = field(default_factory=frozenset)
    order_index: int = 0
    kind: ModuleKind = field(default=ModuleKind.PAGE, init=False)


@dataclass(frozen=True, slots=True)
class WorkspaceDescriptor:
    """Descriptor for a multi-route workspace (e.g. Stitch) sharing a single host."""

    module_id: str
    title: str
    category: ModuleCategory
    factory: ModuleFactory
    icon_name: str = "box"
    search_terms: tuple[str, ...] = ()
    capability_flags: frozenset[str] = field(default_factory=frozenset)
    order_index: int = 0
    kind: ModuleKind = field(default=ModuleKind.WORKSPACE, init=False)


@dataclass(frozen=True, slots=True)
class RouteDescriptor:
    """Descriptor for a sub-route targeting a parent WorkspaceDescriptor."""

    module_id: str
    workspace_id: str
    route_key: str
    title: str
    category: ModuleCategory
    icon_name: str = "box"
    search_terms: tuple[str, ...] = ()
    capability_flags: frozenset[str] = field(default_factory=frozenset)
    order_index: int = 0
    kind: ModuleKind = field(default=ModuleKind.ROUTE, init=False)


CatalogDescriptor = PageDescriptor | WorkspaceDescriptor | RouteDescriptor


class ModuleCatalog:
    """App-scoped catalog. It has no global instance and owns no widgets."""

    def __init__(self) -> None:
        self._descriptors: dict[str, CatalogDescriptor] = {}
        self._order: list[str] = []

    def register(self, descriptor: CatalogDescriptor | ModuleDescriptor) -> None:
        """Register a descriptor. Enforces workspace presence for child routes."""
        if isinstance(descriptor, ModuleDescriptor):
            for desc in self._convert_module_descriptor(descriptor):
                self.register(desc)
            return

        if descriptor.module_id in self._descriptors:
            raise ValueError(f"Duplicate module ID: {descriptor.module_id}")
        if isinstance(descriptor, RouteDescriptor):
            workspace = self._descriptors.get(descriptor.workspace_id)
            if not isinstance(workspace, WorkspaceDescriptor):
                raise ValueError(
                    f"Route {descriptor.module_id} requires registered workspace {descriptor.workspace_id}"
                )
        self._descriptors[descriptor.module_id] = descriptor
        self._order.append(descriptor.module_id)

    def get(self, module_id: str) -> Optional[CatalogDescriptor]:
        """Look up a descriptor by its module_id, supporting both dot and slash routes."""
        if module_id in self._descriptors:
            return self._descriptors[module_id]
        if "/" in module_id:
            normalized = module_id.replace("/", ".")
            return self._descriptors.get(normalized)
        return None

    def require(self, module_id: str) -> CatalogDescriptor:
        """Look up a descriptor, raising LookupError if missing."""
        descriptor = self.get(module_id)
        if descriptor is None:
            raise LookupError(f"Unknown module: {module_id}")
        return descriptor

    def require_workspace(self, module_id: str) -> WorkspaceDescriptor:
        """Look up a workspace descriptor, raising TypeError if not a workspace."""
        descriptor = self.require(module_id)
        if not isinstance(descriptor, WorkspaceDescriptor):
            raise TypeError(f"Module {module_id!r} is not a workspace")
        return descriptor

    def all_descriptors(self) -> tuple[CatalogDescriptor, ...]:
        """Return all registered descriptors in insertion order."""
        return tuple(self._descriptors[module_id] for module_id in self._order)

    def by_category(self, category: ModuleCategory) -> tuple[CatalogDescriptor, ...]:
        """Return all registered descriptors belonging to a category."""
        return tuple(d for d in self.all_descriptors() if d.category == category)

    def search(self, query: str) -> tuple[CatalogDescriptor, ...]:
        """Search descriptors by module_id, title, category, or search terms."""
        needle = query.strip().lower()
        if not needle:
            return self.all_descriptors()
        return tuple(
            descriptor
            for descriptor in self.all_descriptors()
            if needle in descriptor.module_id.lower()
            or needle in descriptor.title.lower()
            or needle in descriptor.category.value.lower()
            or any(needle in term.lower() for term in descriptor.search_terms)
        )

    def _convert_module_descriptor(self, descriptor: ModuleDescriptor) -> list[CatalogDescriptor]:
        from .runtime import WidgetHandle

        if descriptor.child_routes:
            def _ws_factory(_context: ModuleContext) -> ModuleHandle:
                return WidgetHandle(descriptor.get_widget())

            res: list[CatalogDescriptor] = [
                WorkspaceDescriptor(
                    module_id=descriptor.id,
                    title=descriptor.title,
                    category=descriptor.category,
                    factory=_ws_factory,
                    icon_name=descriptor.icon_name,
                    order_index=descriptor.order_index,
                )
            ]
            for r in descriptor.child_routes:
                res.append(
                    RouteDescriptor(
                        module_id=f"{descriptor.id}.{r.route_id}",
                        workspace_id=descriptor.id,
                        route_key=r.route_id,
                        title=r.title,
                        category=descriptor.category,
                        icon_name=descriptor.icon_name,
                        order_index=descriptor.order_index,
                    )
                )
            return res

        def _page_factory(_context: ModuleContext) -> ModuleHandle:
            return WidgetHandle(descriptor.get_widget())

        return [
            PageDescriptor(
                module_id=descriptor.id,
                title=descriptor.title,
                category=descriptor.category,
                factory=_page_factory,
                icon_name=descriptor.icon_name,
                order_index=descriptor.order_index,
            )
        ]


__all__ = [
    "CatalogDescriptor",
    "ModuleCatalog",
    "ModuleCategory",
    "ModuleFactory",
    "ModuleKind",
    "PageDescriptor",
    "RouteDescriptor",
    "WorkspaceDescriptor",
]
