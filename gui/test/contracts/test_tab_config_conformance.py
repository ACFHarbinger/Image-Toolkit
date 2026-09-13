"""Per-tab TabConfig contract conformance (ui-arch-35 / R1.2, #557).

Walks every distinct tab class reachable from the 33-route classic-shell
inventory (``CLASSIC_TAB_ROUTES``) and checks it against the
``collect()``/``set_config()``/``get_default_config()`` contract in
``gui.src.contracts.tab_config``. A tab either fully implements all three
(and is exercised by session recovery, Ctrl+S/Meta+S, and Settings' "Tab
Default Configuration Management") or is explicitly listed in
``_KNOWN_NON_CONFORMING`` with a reason.

This is a *shrinking allowlist*, same pattern as
``check_unauthorized_styling.py``'s styling allowlist: add a tab to
``_KNOWN_NON_CONFORMING`` only with a real reason (not "not done yet"),
and remove an entry the moment that tab gains the contract. New tabs
added to ``CLASSIC_TAB_ROUTES`` must conform outright, or be added here
with a reason -- they may not silently join the unverified set.
"""

from __future__ import annotations

from gui.src.modules.tab_factory import _load_tab_class
from gui.src.windows.main._tab_registry import CLASSIC_TAB_ROUTES

# factory_id -> reason. As of 2026-09-13 (see #557), these 7 have no
# collect()/set_config()/get_default_config() at all -- not a partial
# implementation, a real gap. The three in-app tabs originally flagged as
# product gaps (library.data-browser, web.entity-recon, web.media-loader)
# gained the contract the same day; what remains here is the ASP/CSG/HIE
# submodule surface, out of this roadmap's direct scope -- still listed
# rather than silently passing.
_KNOWN_NON_CONFORMING: dict[str, str] = {
    "editor.hybrid": "no TabConfig contract yet (HIE submodule surface, #557)",
    "manga.animation": "no TabConfig contract yet (ASP/manga submodule surface, #557)",
    "manga.colorization": "no TabConfig contract yet (ASP/manga submodule surface, #557)",
    "manga.puppeteering": "no TabConfig contract yet (ASP/manga submodule surface, #557)",
    "ml.comfyui": "no TabConfig contract yet (comfy generation surface, #557)",
}

_CONTRACT_METHODS = ("collect", "set_config", "get_default_config")

# ExtractorTab (system.extractor) is a thin QWidget wrapper around
# VideoExtractorSubTab + ImageExtractorSubTab; get_default_config() isn't
# declared on the wrapper class itself but resolves at the instance level
# via its __getattr__ delegation to video_subtab (confirmed: ExtractorTab()
# needs no constructor args, so this is checked directly rather than
# trusted). A plain hasattr(cls, ...) class-level check can't see this --
# it never triggers __getattr__ -- so it's verified separately below
# instead of joining _KNOWN_NON_CONFORMING (which is for tabs that
# genuinely don't implement the contract anywhere in their delegation
# chain, not a test-methodology gap).
_DELEGATED_AT_INSTANCE_LEVEL = {"system.extractor"}


def _distinct_factory_ids() -> list[str]:
    return sorted({factory_id for _mid, _cat, _title, _expr, factory_id in CLASSIC_TAB_ROUTES})


def test_inventory_has_33_routes_mapping_to_known_factory_count():
    assert len(CLASSIC_TAB_ROUTES) == 33
    # Stitch's 8 sub-panel routes all share one workspace factory_id, so the
    # distinct-class count is lower than 33 -- pin the current shape so a
    # registry change is a deliberate, reviewed edit to this test too.
    assert len(_distinct_factory_ids()) == 26


def test_every_conforming_tab_implements_the_full_contract():
    """Every factory_id not in _KNOWN_NON_CONFORMING must fully conform."""
    failures = []
    for factory_id in _distinct_factory_ids():
        if factory_id in _KNOWN_NON_CONFORMING or factory_id in _DELEGATED_AT_INSTANCE_LEVEL:
            continue
        cls = _load_tab_class(factory_id)
        missing = [m for m in _CONTRACT_METHODS if not hasattr(cls, m)]
        if missing:
            failures.append(f"{factory_id} ({cls.__qualname__}): missing {missing}")
    assert not failures, "TabConfig contract violations:\n" + "\n".join(failures)


def test_extractor_tab_resolves_get_default_config_via_delegation(q_app):
    """system.extractor's ExtractorTab wrapper doesn't declare
    get_default_config() itself but must resolve it at the instance level
    via __getattr__ delegation to video_subtab -- verify it actually works,
    not just that the class has a __getattr__ to hope with."""
    from gui.src.tabs.core.extractor_tab.wrapper import ExtractorTab

    tab = ExtractorTab()
    assert hasattr(tab, "get_default_config")
    config = tab.get_default_config()
    assert isinstance(config, dict)


def test_known_non_conforming_list_is_accurate_not_stale():
    """Every _KNOWN_NON_CONFORMING entry must still actually be non-conforming.

    Catches the exact staleness this whole conformance check exists to
    prevent: an entry left in the allowlist after the tab was fixed.
    """
    stale = []
    for factory_id in _KNOWN_NON_CONFORMING:
        cls = _load_tab_class(factory_id)
        missing = [m for m in _CONTRACT_METHODS if not hasattr(cls, m)]
        if not missing:
            stale.append(factory_id)
    assert not stale, f"These factory_ids now fully conform -- remove from _KNOWN_NON_CONFORMING: {stale}"


def test_known_non_conforming_ids_are_real_routes():
    """Every _KNOWN_NON_CONFORMING key must be a real, current factory_id."""
    valid = set(_distinct_factory_ids())
    unknown = set(_KNOWN_NON_CONFORMING) - valid
    assert not unknown, f"_KNOWN_NON_CONFORMING references non-existent factory_ids: {unknown}"
