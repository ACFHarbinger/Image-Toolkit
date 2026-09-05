"""gui/src/modules/registry.py
===========================
ModuleRegistry managing module discovery and route resolution (§1.3, #527).
"""

from __future__ import annotations

from threading import RLock
from typing import Optional

from .descriptor import ModuleCategory, ModuleDescriptor, ModuleRoute


class ModuleRegistry:
    """Registry maintaining active ModuleDescriptors and route mappings."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._modules: dict[str, ModuleDescriptor] = {}

    def register(self, descriptor: ModuleDescriptor) -> None:
        """Register a module descriptor."""
        with self._lock:
            self._modules[descriptor.id] = descriptor

    def unregister(self, module_id: str) -> None:
        """Unregister a module by its identifier."""
        with self._lock:
            self._modules.pop(module_id, None)

    def get(self, module_id: str) -> Optional[ModuleDescriptor]:
        """Retrieve a descriptor by ID."""
        with self._lock:
            return self._modules.get(module_id)

    def all_modules(self) -> list[ModuleDescriptor]:
        """Return all registered descriptors ordered by order_index."""
        with self._lock:
            return sorted(self._modules.values(), key=lambda m: m.order_index)

    def by_category(self, category: ModuleCategory) -> list[ModuleDescriptor]:
        """Return all registered modules belonging to a category."""
        with self._lock:
            return [
                m
                for m in sorted(self._modules.values(), key=lambda m: m.order_index)
                if m.category == category
            ]

    def search(self, query: str) -> list[ModuleDescriptor]:
        """Fuzzy search across title, ID, and description."""
        q = query.lower().strip()
        with self._lock:
            return [
                m
                for m in self.all_modules()
                if q in m.title.lower()
                or q in m.id.lower()
                or (m.japanese_subtext and q in m.japanese_subtext.lower())
            ]

    def resolve_route(self, route: str) -> tuple[Optional[ModuleDescriptor], Optional[ModuleRoute]]:
        """Resolve a route string into its owning module and optional child route.

        Supports formats:
          - "module_id" -> (descriptor, None)
          - "module_id/child_route_id" -> (descriptor, child_route)
        """
        clean_route = route.strip().strip("/")
        if not clean_route:
            return (None, None)

        if "/" in clean_route:
            mod_id, child_id = clean_route.split("/", 1)
        else:
            mod_id, child_id = clean_route, ""

        with self._lock:
            desc = self._modules.get(mod_id)
            if desc is None:
                return (None, None)

            if not child_id:
                return (desc, None)

            child = desc.get_child_route(child_id)
            if child is None:
                # A child route was explicitly requested but doesn't exist
                # on this module -- this must read as "no match" (#527
                # cross-review), not silently resolve to the top-level
                # module route. Returning (desc, None) here would be
                # indistinguishable from "no child requested at all" to
                # ModuleHostWidget.navigate_to(), which would then mount
                # and activate the module as if the invalid route were valid.
                return (None, None)
            return (desc, child)

    def clear(self) -> None:
        """Clear all registered modules."""
        with self._lock:
            self._modules.clear()


__all__ = ["ModuleRegistry"]
