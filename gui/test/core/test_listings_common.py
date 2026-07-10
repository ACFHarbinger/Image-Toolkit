from gui.src.tabs.core.elements.common.listings_common import (
    resolve_entity_id_for_mal_name,
)


def test_resolve_entity_id_exact_match():
    index = {"tomoko tomoko": "e1", "yuki tanaka": "e2"}
    assert resolve_entity_id_for_mal_name("Tomoko Tomoko", index) == "e1"


def test_resolve_entity_id_single_mal_name_matches_duplicated_entity():
    index = {"tomoko tomoko": "e-tomoko", "sakura kinomoto": "e-sakura"}
    assert resolve_entity_id_for_mal_name("Tomoko", index) == "e-tomoko"


def test_resolve_entity_id_reversed_multi_word_name():
    index = {"yuki tanaka": "e-yuki"}
    assert resolve_entity_id_for_mal_name("Tanaka Yuki", index) == "e-yuki"


def test_resolve_entity_id_last_first_comma_form():
    index = {"hayao miyazaki": "e-hayao"}
    assert resolve_entity_id_for_mal_name("Miyazaki, Hayao", index) == "e-hayao"


def test_resolve_entity_id_returns_none_when_unmatched():
    index = {"tomoko tomoko": "e1"}
    assert resolve_entity_id_for_mal_name("Unknown", index) is None