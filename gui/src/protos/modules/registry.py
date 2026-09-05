"""Module Registry for plug-and-play tools and dynamic shell navigation (§2.36)."""

from __future__ import annotations

from typing import Optional

from .descriptor import ModuleCategory, ModuleDescriptor


class ModuleRegistry:
    """Global/Host registry storing all available tool descriptors."""

    _instance: Optional[ModuleRegistry] = None

    def __init__(self) -> None:
        self._modules: dict[str, ModuleDescriptor] = {}
        self._order: list[str] = []

    @classmethod
    def instance(cls) -> ModuleRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, descriptor: ModuleDescriptor) -> None:
        """Register a tool descriptor."""
        self._modules[descriptor.id] = descriptor
        if descriptor.id not in self._order:
            self._order.append(descriptor.id)

    def get(self, module_id: str) -> Optional[ModuleDescriptor]:
        """Retrieve a descriptor by its ID."""
        return self._modules.get(module_id)

    def all_modules(self) -> list[ModuleDescriptor]:
        """Return all registered modules in order."""
        return [self._modules[mid] for mid in self._order if mid in self._modules]

    def by_category(self, category: ModuleCategory) -> list[ModuleDescriptor]:
        """Return all modules under a specific category."""
        return [m for m in self.all_modules() if m.category == category]

    def categories(self) -> list[ModuleCategory]:
        """Return all unique categories present in the registry."""
        seen = []
        for m in self.all_modules():
            if m.category not in seen:
                seen.append(m.category)
        return seen

    def search(self, query: str) -> list[ModuleDescriptor]:
        """Search modules by title, ID, category, or Japanese subtext."""
        q = query.strip().lower()
        if not q:
            return self.all_modules()
        results = []
        for m in self.all_modules():
            match_fields = [
                m.id.lower(),
                m.title.lower(),
                m.category.value.lower(),
                (m.japanese_subtext or "").lower(),
            ]
            if any(q in field for field in match_fields):
                results.append(m)
        return results

    def clear(self) -> None:
        """Clear all registrations."""
        self._modules.clear()
        self._order.clear()


__all__ = ["ModuleRegistry"]
