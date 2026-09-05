"""Immutable module, workspace, and route metadata owned by one app."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

from .descriptor import ModuleCategory

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

    def register(self, descriptor: CatalogDescriptor) -> None:
        if descriptor.module_id in self._descriptors:
            raise ValueError(f"Duplicate module ID: {descriptor.module_id}")
        if isinstance(descriptor, RouteDescriptor):
            workspace = self._descriptors.get(descriptor.workspace_id)
            if not isinstance(workspace, WorkspaceDescriptor):
                raise ValueError(f"Route {descriptor.module_id} requires registered workspace {descriptor.workspace_id}")
        self._descriptors[descriptor.module_id] = descriptor
        self._order.append(descriptor.module_id)

    def get(self, module_id: str) -> CatalogDescriptor | None:
        return self._descriptors.get(module_id)

    def require(self, module_id: str) -> CatalogDescriptor:
        descriptor = self.get(module_id)
        if descriptor is None:
            raise LookupError(f"Unknown module: {module_id}")
        return descriptor

    def require_workspace(self, module_id: str) -> WorkspaceDescriptor:
        descriptor = self.require(module_id)
        if not isinstance(descriptor, WorkspaceDescriptor):
            raise TypeError(f"Module {module_id!r} is not a workspace")
        return descriptor

    def all_descriptors(self) -> tuple[CatalogDescriptor, ...]:
        return tuple(self._descriptors[module_id] for module_id in self._order)

    def categories(self) -> tuple[ModuleCategory, ...]:
        return tuple(dict.fromkeys(descriptor.category for descriptor in self.all_descriptors()))

    def by_category(self, category: ModuleCategory) -> tuple[CatalogDescriptor, ...]:
        return tuple(descriptor for descriptor in self.all_descriptors() if descriptor.category == category)

    def search(self, query: str) -> tuple[CatalogDescriptor, ...]:
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


__all__ = [
    "CatalogDescriptor",
    "ModuleCatalog",
    "ModuleFactory",
    "ModuleKind",
    "PageDescriptor",
    "RouteDescriptor",
    "WorkspaceDescriptor",
]
