"""Structural anti-eager-mounting contract tests (§2.36, #533).

Asserts that catalog creation, runtime initialization, metadata queries,
and route resolution structurally invoke zero widget factories.
Only explicit navigation/activation invokes the target factory, and
multi-route workspaces share a single host handle without duplicated mounts.
"""

from __future__ import annotations

import pytest
from gui.src.modules import (
    ModuleCatalog,
    ModuleCategory,
    ModuleContext,
    ModuleDeactivated,
    ModuleKind,
    ModuleRuntime,
    ModuleServices,
    PageDescriptor,
    RouteDescriptor,
    WidgetHandle,
    WorkspaceDescriptor,
    build_application_catalog,
)
from gui.src.modules.events import EventHub, ModuleActivated
from gui.src.modules.stitch_workspace import stitch_workspace_enabled
from gui.src.preferences import MemoryPreferenceAdapter, PreferenceScope, PreferenceStore, PrefKeys
from PySide6.QtWidgets import QApplication, QLabel


class CountingHandle(WidgetHandle):
    """Lifecycle handle recording activation, deactivation, and disposal."""

    def __init__(self, label: str) -> None:
        super().__init__(QLabel(label))
        self.label = label
        self.activations: list[str | None] = []
        self.deactivations = 0
        self.disposals = 0

    def activate(self, route_key: str | None = None) -> None:
        self.activations.append(route_key)

    def deactivate(self) -> None:
        self.deactivations += 1

    def dispose(self) -> None:
        self.disposals += 1
        super().dispose()


@pytest.fixture
def module_context(q_app) -> ModuleContext:
    return ModuleContext(
        event_hub=EventHub(q_app),
        services=ModuleServices(),
        account_id="test-account",
    )


def test_catalog_construction_and_registration_invokes_zero_factories():
    """Registering pages, workspaces, and routes must never invoke factories."""
    catalog = ModuleCatalog()
    call_counts: dict[str, int] = {}

    def make_factory(mod_id: str):
        def _factory(context: ModuleContext):
            call_counts[mod_id] = call_counts.get(mod_id, 0) + 1
            return CountingHandle(mod_id)

        return _factory

    for i in range(10):
        mod_id = f"page_{i}"
        catalog.register(
            PageDescriptor(
                module_id=mod_id,
                title=f"Page {i}",
                category=ModuleCategory.SYSTEM,
                factory=make_factory(mod_id),
            )
        )

    for i in range(3):
        ws_id = f"ws_{i}"
        catalog.register(
            WorkspaceDescriptor(
                module_id=ws_id,
                title=f"Workspace {i}",
                category=ModuleCategory.STITCHING,
                factory=make_factory(ws_id),
            )
        )
        for r in ("a", "b", "c"):
            route_id = f"{ws_id}.{r}"
            catalog.register(
                RouteDescriptor(
                    module_id=route_id,
                    workspace_id=ws_id,
                    route_key=r,
                    title=f"Route {r}",
                    category=ModuleCategory.STITCHING,
                )
            )

    assert len(catalog.all_descriptors()) == 10 + 3 + 9
    assert call_counts == {}, "Factories were eagerly invoked during catalog registration"


def test_runtime_initialization_and_metadata_queries_invoke_zero_factories(module_context):
    """Constructing runtime and querying metadata must invoke zero factories."""
    catalog = ModuleCatalog()
    call_counts: dict[str, int] = {}

    def make_factory(mod_id: str):
        def _factory(context: ModuleContext):
            call_counts[mod_id] = call_counts.get(mod_id, 0) + 1
            return CountingHandle(mod_id)

        return _factory

    catalog.register(
        PageDescriptor(
            module_id="mod_a",
            title="Module A",
            category=ModuleCategory.LIBRARY,
            factory=make_factory("mod_a"),
        )
    )
    catalog.register(
        PageDescriptor(
            module_id="mod_b",
            title="Module B",
            category=ModuleCategory.LIBRARY,
            factory=make_factory("mod_b"),
        )
    )

    runtime = ModuleRuntime(catalog, module_context)

    # Invariants before any activation
    assert runtime.active_module_id is None
    assert runtime.is_created("mod_a") is False
    assert runtime.is_created("mod_b") is False
    assert catalog.get("mod_a") is not None
    assert catalog.require("mod_b").title == "Module B"
    assert len(catalog.search("Module")) == 2
    assert len(catalog.by_category(ModuleCategory.LIBRARY)) == 2
    assert call_counts == {}, "Factories were invoked during metadata lookup or runtime init"


def test_activation_is_strictly_lazy_and_caches_instance(module_context):
    """Activating mod_a must instantiate only mod_a, leaving mod_b uncreated."""
    catalog = ModuleCatalog()
    call_counts: dict[str, int] = {}

    def make_factory(mod_id: str):
        def _factory(context: ModuleContext):
            call_counts[mod_id] = call_counts.get(mod_id, 0) + 1
            return CountingHandle(mod_id)

        return _factory

    catalog.register(
        PageDescriptor(
            module_id="mod_a",
            title="Module A",
            category=ModuleCategory.LIBRARY,
            factory=make_factory("mod_a"),
        )
    )
    catalog.register(
        PageDescriptor(
            module_id="mod_b",
            title="Module B",
            category=ModuleCategory.LIBRARY,
            factory=make_factory("mod_b"),
        )
    )

    activated_facts: list[ModuleActivated] = []
    module_context.event_hub.subscribe(ModuleActivated, activated_facts.append)

    runtime = ModuleRuntime(catalog, module_context)

    h_a1 = runtime.activate("mod_a")
    assert call_counts == {"mod_a": 1}
    assert runtime.is_created("mod_a") is True
    assert runtime.is_created("mod_b") is False
    assert runtime.active_module_id == "mod_a"
    assert len(activated_facts) == 1
    assert activated_facts[0].module_id == "mod_a"

    # Repeated activation reuses the cached handle without invoking factory again
    h_a2 = runtime.activate("mod_a")
    assert h_a1 is h_a2
    assert call_counts == {"mod_a": 1}
    assert runtime.is_created("mod_b") is False


def test_workspace_routes_share_single_host_without_duplicate_instantiation(module_context):
    """Activating routes within a workspace must instantiate the workspace host exactly once."""
    catalog = ModuleCatalog()
    call_counts: dict[str, int] = {}

    def ws_factory(context: ModuleContext):
        call_counts["stitch"] = call_counts.get("stitch", 0) + 1
        return CountingHandle("stitch_workspace")

    catalog.register(
        WorkspaceDescriptor(
            module_id="stitch",
            title="Image Stitching",
            category=ModuleCategory.STITCHING,
            factory=ws_factory,
        )
    )
    for key in ("adjust", "canvas", "graph", "stats"):
        catalog.register(
            RouteDescriptor(
                module_id=f"stitch.{key}",
                workspace_id="stitch",
                route_key=key,
                title=key.title(),
                category=ModuleCategory.STITCHING,
            )
        )

    runtime = ModuleRuntime(catalog, module_context)

    assert call_counts == {}
    assert runtime.is_created("stitch") is False
    assert runtime.is_created("stitch.adjust") is False

    # First route activation creates the workspace handle
    h_adjust = runtime.activate("stitch.adjust")
    assert call_counts == {"stitch": 1}
    assert runtime.is_created("stitch") is True
    assert runtime.is_created("stitch.adjust") is True
    assert runtime.is_created("stitch.canvas") is True
    assert h_adjust.activations == ["adjust"]
    assert h_adjust.deactivations == 0

    # Activating sibling route reuses the identical handle
    h_canvas = runtime.activate("stitch.canvas")
    assert h_canvas is h_adjust
    assert call_counts == {"stitch": 1}, "Workspace factory ran more than once for sibling route"
    assert h_canvas.activations == ["adjust", "canvas"]
    assert h_canvas.deactivations == 0, "Deactivation occurred between sibling routes on same workspace"


def test_switching_modules_deactivates_previous_and_keeps_unvisited_unmounted(module_context):
    """Switching between modules deactivates the previous module without touching unvisited ones."""
    catalog = ModuleCatalog()
    handles: dict[str, CountingHandle] = {}

    def make_factory(mod_id: str):
        def _factory(context: ModuleContext):
            h = CountingHandle(mod_id)
            handles[mod_id] = h
            return h

        return _factory

    for name in ("one", "two", "three"):
        catalog.register(
            PageDescriptor(
                module_id=name,
                title=name,
                category=ModuleCategory.SYSTEM,
                factory=make_factory(name),
            )
        )

    deactivated_facts: list[ModuleDeactivated] = []
    module_context.event_hub.subscribe(ModuleDeactivated, deactivated_facts.append)

    runtime = ModuleRuntime(catalog, module_context)

    runtime.activate("one")
    assert list(handles.keys()) == ["one"]
    assert handles["one"].activations == [None]
    assert handles["one"].deactivations == 0

    runtime.activate("two")
    assert list(handles.keys()) == ["one", "two"]
    assert handles["one"].deactivations == 1
    assert handles["two"].activations == [None]
    assert len(deactivated_facts) == 1
    assert deactivated_facts[0].module_id == "one"

    # Module "three" was never visited and must never have been instantiated
    assert "three" not in handles
    assert runtime.is_created("three") is False


def test_runtime_dispose_disposes_only_created_modules(module_context):
    """Disposing runtime must dispose active/cached modules without instantiating unvisited ones."""
    catalog = ModuleCatalog()
    handles: dict[str, CountingHandle] = {}

    def make_factory(mod_id: str):
        def _factory(context: ModuleContext):
            h = CountingHandle(mod_id)
            handles[mod_id] = h
            return h

        return _factory

    for name in ("alpha", "beta", "gamma"):
        catalog.register(
            PageDescriptor(
                module_id=name,
                title=name,
                category=ModuleCategory.SYSTEM,
                factory=make_factory(name),
            )
        )

    runtime = ModuleRuntime(catalog, module_context)
    runtime.activate("alpha")

    assert set(handles.keys()) == {"alpha"}
    runtime.dispose()

    assert handles["alpha"].deactivations == 1
    assert handles["alpha"].disposals == 1
    assert "beta" not in handles
    assert "gamma" not in handles
    assert runtime.is_created("alpha") is False
    assert runtime.active_module_id is None


def test_application_catalog_contains_all_33_routes_without_eager_mounting(q_app):
    """Verify build_application_catalog registers all 33 routes with zero widget instantiation."""
    before = set(map(id, QApplication.allWidgets()))
    catalog = build_application_catalog(dropdown=True, enable_manager=False, enable_stitch=True)
    created = [w for w in QApplication.allWidgets() if id(w) not in before]
    assert created == [], f"catalog construction eagerly mounted widgets: {created!r}"
    descriptors = catalog.all_descriptors()

    # 25 pages + 1 workspace + 8 routes = 34 total descriptors
    assert len(descriptors) == 34

    # 33 navigable routes (pages + routes, excluding workspace container)
    navigable = [d for d in descriptors if d.kind != ModuleKind.WORKSPACE]
    assert len(navigable) == 33

    # Check key routes across categories
    assert catalog.require("system.convert").title == "Convert"
    assert catalog.require("system.wallpaper").title == "Wallpaper"
    assert catalog.require("library.listings").title == "Listings"
    assert catalog.require("library.search").title == "Image Search"
    assert catalog.require("library.scan").title == "Scan and Tag"
    assert catalog.require("library.management").title == "Management"
    assert catalog.require("web.crawler").title == "Crawler"
    assert catalog.require("ml.training").title == "Training"
    assert catalog.require("stitch.stitch").title == "Stitch"
    assert catalog.require("stitch.canvas").title == "Canvas"
    assert catalog.require("manga.colorization").title == "Colorization"
    assert catalog.require("editor.hybrid").title == "Hybrid Editor"


def test_stitch_routes_are_account_gated_but_inventory_can_opt_in(q_app):
    store = PreferenceStore(lazy_adapters=True)
    store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())

    assert stitch_workspace_enabled(store) is False
    assert build_application_catalog(preference_store=store).get("stitch.canvas") is None

    store.set(PrefKeys.EXPERIMENTAL_STITCH_WORKSPACE, True)
    assert stitch_workspace_enabled(store) is True
    assert build_application_catalog(preference_store=store).get("stitch.canvas") is not None
