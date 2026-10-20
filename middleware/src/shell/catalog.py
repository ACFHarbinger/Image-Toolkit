"""Serializable module catalog (W0-05, #869).

This is the only route-id registry. ``entry.id`` is the ledger id #882
must reuse. Widget factories stay in ``gui/``. #870 reads
``shell_catalog().to_document()``; it must not grow a second id list.

Window roles are the small set from the locked shell decision: the main
webview, the tray, the slideshow presenter, and labeled pop-outs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Iterable


class ModuleCategory(str, Enum):
    """Functional categories for application modules."""

    SYSTEM = "System Tools"
    LIBRARY = "Library Database"
    WEB = "Web Integration"
    DEEP_LEARNING = "Deep Learning"
    STITCHING = "Image Stitching"
    MANGA = "Manga"
    EDITOR = "Image Editor"
    DEVELOPER = "Developer / Diagnostics"


class CatalogKind(str, Enum):
    PAGE = "page"
    WORKSPACE = "workspace"
    ROUTE = "route"


class WindowRole(str, Enum):
    MAIN = "main"
    TRAY = "tray"
    SLIDESHOW = "slideshow"
    POPOUT = "popout"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One navigable id. No widget, no factory, no Qt type."""

    id: str
    title: str
    category: ModuleCategory
    kind: CatalogKind
    order_index: int
    window_id: str = "main"
    workspace_id: str | None = None
    route_key: str | None = None
    icon_name: str = "box"
    capability_flags: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()
    surfaces: tuple[str, ...] = ("qt", "frontend")
    legacy_frontend_id: str | None = None
    companion_window_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["kind"] = self.kind.value
        payload["capability_flags"] = list(self.capability_flags)
        payload["search_terms"] = list(self.search_terms)
        payload["surfaces"] = list(self.surfaces)
        return payload


@dataclass(frozen=True, slots=True)
class CatalogAlias:
    """Old id that resolves to ``target_id`` when ``applies_when`` holds."""

    alias_id: str
    target_id: str
    applies_when: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CatalogWindow:
    """A native window role. Not a route."""

    id: str
    role: WindowRole
    panel_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role.value, "panel_of": self.panel_of}


def _page(
    module_id: str,
    title: str,
    category: ModuleCategory,
    order_index: int,
    *,
    legacy_frontend_id: str | None = None,
    companion_window_id: str | None = None,
    surfaces: tuple[str, ...] = ("qt", "frontend"),
    icon_name: str = "box",
) -> CatalogEntry:
    return CatalogEntry(
        id=module_id,
        title=title,
        category=category,
        kind=CatalogKind.PAGE,
        order_index=order_index,
        legacy_frontend_id=legacy_frontend_id,
        companion_window_id=companion_window_id,
        surfaces=surfaces,
        icon_name=icon_name,
    )


def _workspace(
    module_id: str,
    title: str,
    category: ModuleCategory,
    *,
    icon_name: str,
    search_terms: tuple[str, ...],
    capability_flags: tuple[str, ...] = ("experimental",),
) -> CatalogEntry:
    return CatalogEntry(
        id=module_id,
        title=title,
        category=category,
        kind=CatalogKind.WORKSPACE,
        order_index=0,
        icon_name=icon_name,
        capability_flags=capability_flags,
        search_terms=search_terms,
    )


def _route(
    module_id: str,
    route_key: str,
    title: str,
    category: ModuleCategory,
    workspace_id: str,
    order_index: int,
    *,
    icon_name: str,
    search_terms: tuple[str, ...],
) -> CatalogEntry:
    return CatalogEntry(
        id=module_id,
        title=title,
        category=category,
        kind=CatalogKind.ROUTE,
        order_index=order_index,
        workspace_id=workspace_id,
        route_key=route_key,
        icon_name=icon_name,
        capability_flags=("experimental",),
        search_terms=search_terms,
    )


def _entries() -> tuple[CatalogEntry, ...]:
    """Ids and titles match the live Qt inventory. Do not mint a parallel list."""
    system = ModuleCategory.SYSTEM
    library = ModuleCategory.LIBRARY
    web = ModuleCategory.WEB
    deep = ModuleCategory.DEEP_LEARNING
    stitch = ModuleCategory.STITCHING
    manga = ModuleCategory.MANGA
    editor = ModuleCategory.EDITOR
    pages = (
        _page("system.convert", "Convert", system, 0, legacy_frontend_id="convert"),
        _page("system.merge", "Merge", system, 1, legacy_frontend_id="merge"),
        _page("system.similarity", "Similarity", system, 2, legacy_frontend_id="delete"),
        _page("system.extractor", "Extractor", system, 3, legacy_frontend_id="extractor"),
        _page(
            "system.wallpaper",
            "Wallpaper",
            system,
            4,
            legacy_frontend_id="wallpaper",
            companion_window_id="slideshow",
        ),
        _page("library.listings", "Listings", library, 5),
        _page("library.search", "Image Search", library, 6, legacy_frontend_id="search"),
        _page("library.scan", "Scan and Tag", library, 7, legacy_frontend_id="scan"),
        _page("library.management", "Management", library, 8, legacy_frontend_id="database"),
        _page("library.data-browser", "Data Browser", library, 9),
        _page("web.crawler", "Crawler", web, 10, legacy_frontend_id="crawler"),
        _page("web.requests", "Requests", web, 11, legacy_frontend_id="webreq"),
        _page("web.drive-sync", "Cloud Synchronization", web, 12, legacy_frontend_id="drive"),
        _page("web.media-loader", "Media Loader", web, 13),
        _page("web.reverse-search", "Reverse Search", web, 14, legacy_frontend_id="revsearch"),
        _page("web.entity-recon", "Entity Reconnaissance", web, 15),
        _page("ml.training", "Training", deep, 16, legacy_frontend_id="train"),
        _page("ml.generation", "Generation", deep, 17, legacy_frontend_id="generate"),
        _page("ml.evaluation", "Evaluation", deep, 18, legacy_frontend_id="evaluate"),
        _page("ml.inference", "Inference", deep, 19, legacy_frontend_id="inference"),
        _page("ml.comfyui", "ComfyUI", deep, 20),
        _page("manga.colorization", "Colorization", manga, 21),
        _page("manga.animation", "Animation", manga, 22),
        _page("manga.puppeteering", "Puppeteering", manga, 23),
        _page("editor.hybrid", "Hybrid Editor", editor, 24, legacy_frontend_id="hie_editor", icon_name="layers"),
        _page(
            "developer.benchmarks",
            "Benchmarks",
            ModuleCategory.DEVELOPER,
            25,
            legacy_frontend_id="benchmarks",
            surfaces=("frontend",),
            icon_name="chart",
        ),
    )
    stitch_workspace = _workspace(
        "stitch",
        "Image Stitching",
        stitch,
        icon_name="layers",
        search_terms=("stitch", "panorama", "anime"),
    )
    stitch_routes = (
        ("stitch.stitch", "stitch", "Stitch"),
        ("stitch.graph", "graph", "Graph"),
        ("stitch.adjust", "adjust", "Adjust"),
        ("stitch.canvas", "canvas", "Canvas"),
        ("stitch.statistics", "statistics", "Statistics"),
        ("stitch.sequence-builder", "sequence-builder", "Sequence Builder"),
        ("stitch.hybrid", "hybrid", "Hybrid Stitch"),
        ("stitch.animation-clusters", "animation-clusters", "Animation Clusters"),
    )
    dl_workspace = _workspace(
        "dl",
        "Deep Learning",
        deep,
        icon_name="cpu",
        search_terms=("train", "lora", "comfy", "generate"),
    )
    dl_routes = (
        ("dl.train", "train", "Train"),
        ("dl.generate", "generate", "Generate"),
        ("dl.review", "review", "Review"),
        ("dl.runs", "runs", "Runs"),
    )
    extra: list[CatalogEntry] = [stitch_workspace, dl_workspace]
    extra.extend(
        _route(
            module_id,
            route_key,
            title,
            stitch,
            "stitch",
            index,
            icon_name="layers",
            search_terms=("stitch", route_key),
        )
        for index, (module_id, route_key, title) in enumerate(stitch_routes)
    )
    extra.extend(
        _route(
            module_id,
            route_key,
            title,
            deep,
            "dl",
            index,
            icon_name="cpu",
            search_terms=("deep learning", route_key),
        )
        for index, (module_id, route_key, title) in enumerate(dl_routes)
    )
    return pages + tuple(extra)


_ALIASES = (
    CatalogAlias("ml.training", "dl.train", "experimental-dl"),
    CatalogAlias("ml.generation", "dl.generate", "experimental-dl"),
    CatalogAlias("ml.evaluation", "dl.review", "experimental-dl"),
    CatalogAlias("ml.inference", "dl.review", "experimental-dl"),
    CatalogAlias("ml.comfyui", "dl.generate", "experimental-dl"),
)

_WINDOWS = (
    CatalogWindow("main", WindowRole.MAIN),
    CatalogWindow("tray", WindowRole.TRAY),
    CatalogWindow("slideshow", WindowRole.SLIDESHOW),
    CatalogWindow("cloud.jobs", WindowRole.POPOUT, panel_of="main"),
)


class ShellCatalog:
    """Immutable document. Both shells render this; only Qt attaches factories."""

    def __init__(
        self,
        entries: Iterable[CatalogEntry],
        aliases: Iterable[CatalogAlias],
        windows: Iterable[CatalogWindow],
    ) -> None:
        self.entries = tuple(entries)
        self.aliases = tuple(aliases)
        self.windows = tuple(windows)
        ids = [entry.id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate catalog id")
        known = set(ids)
        window_ids = {window.id for window in self.windows}
        for entry in self.entries:
            if entry.window_id not in window_ids:
                raise ValueError(f"{entry.id} references unknown window {entry.window_id}")
            if entry.companion_window_id and entry.companion_window_id not in window_ids:
                raise ValueError(f"{entry.id} references unknown companion window")
            if entry.kind is CatalogKind.ROUTE and (
                entry.workspace_id not in known or entry.route_key is None
            ):
                raise ValueError(f"route {entry.id} is missing its workspace")
        for alias in self.aliases:
            if alias.target_id not in known:
                raise ValueError(f"alias {alias.alias_id} targets unknown {alias.target_id}")

    def require(self, module_id: str) -> CatalogEntry:
        for entry in self.entries:
            if entry.id == module_id:
                return entry
        raise KeyError(module_id)

    def pages(self) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.entries if entry.kind is CatalogKind.PAGE)

    def alias_map(self, applies_when: str) -> dict[str, str]:
        return {
            alias.alias_id: alias.target_id
            for alias in self.aliases
            if alias.applies_when == applies_when
        }

    def to_document(self) -> dict[str, Any]:
        return {
            "version": 1,
            "entries": [entry.to_dict() for entry in self.entries],
            "aliases": [alias.to_dict() for alias in self.aliases],
            "windows": [window.to_dict() for window in self.windows],
        }


@lru_cache(maxsize=1)
def shell_catalog() -> ShellCatalog:
    return ShellCatalog(_entries(), _ALIASES, _WINDOWS)
