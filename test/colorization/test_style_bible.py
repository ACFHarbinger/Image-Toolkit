import json
import os

import pytest

from colorization.style_bible import (
    CharacterStyleBible,
    MaterialPalette,
    ReferenceView,
    StyleMaterial,
    load_style_bible,
    migrate_style_bible_payload,
    save_style_bible,
)


def _bible():
    return CharacterStyleBible(
        "aiko-tv",
        "Aiko",
        "TV cel",
        [
            StyleMaterial(
                "hair",
                "Hair",
                MaterialPalette("#34283A", "#594B63", "#201827", "#8A7199"),
                ("bangs", "ponytail"),
            ),
            StyleMaterial(
                "skin",
                "Skin",
                MaterialPalette("#E7B49A", "#F4CBB5", "#B87768"),
            ),
        ],
        [ReferenceView("front", "Front turnaround", "references/aiko-front.png")],
    )


def test_round_trip_uses_canonical_json_and_safe_reference_paths(tmp_path):
    path = save_style_bible(tmp_path / "style-bibles/aiko-tv.json", _bible())
    assert load_style_bible(path) == _bible()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["materials"][0]["palette"]["shadow"] == "#201827"
    assert "pixels" not in payload


def test_save_rotates_last_valid_bible_into_bounded_recovery(tmp_path):
    path = tmp_path / "aiko.json"
    save_style_bible(path, _bible())
    changed = _bible()
    changed.style_name = "Feature film cel"
    save_style_bible(path, changed)
    assert load_style_bible(tmp_path / ".recovery/aiko.1.json").style_name == "TV cel"
    assert load_style_bible(path).style_name == "Feature film cel"


def test_interrupted_replace_preserves_last_valid_bible(tmp_path, monkeypatch):
    path = tmp_path / "aiko.json"
    save_style_bible(path, _bible())
    changed = _bible()
    changed.style_name = "Interrupted update"
    monkeypatch.setattr(
        os, "replace", lambda source, destination: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(OSError, match="disk"):
        save_style_bible(path, changed)
    assert load_style_bible(path).style_name == "TV cel"


@pytest.mark.parametrize("color", ["#ffffff", "FFFFFF", "#FFFF", "#GGGGGG"])
def test_palette_rejects_noncanonical_colors(color):
    with pytest.raises(ValueError, match="uppercase"):
        MaterialPalette(color, "#FFFFFF", "#000000")


@pytest.mark.parametrize("path", ["/absolute.png", "../escape.png", "refs\\bad.png", ""])
def test_reference_rejects_unsafe_paths(path):
    with pytest.raises(ValueError, match="safe project-relative"):
        ReferenceView("front", "Front", path)


def test_duplicate_or_ambiguous_material_names_are_rejected():
    bible = _bible()
    bible.materials[1] = StyleMaterial(
        "skin", "Skin", MaterialPalette("#FFFFFF", "#FFFFFF", "#000000"), ("hair",)
    )
    with pytest.raises(ValueError, match="unambiguously"):
        bible.validate()


def test_unknown_or_future_schema_is_rejected():
    payload = _bible().to_dict()
    payload["schema_version"] = 3
    with pytest.raises(ValueError, match="unsupported"):
        CharacterStyleBible.from_dict(payload)
    payload = _bible().to_dict() | {"embedding": [1, 2, 3]}
    with pytest.raises(ValueError, match="unknown fields"):
        CharacterStyleBible.from_dict(payload)


def test_schema_v1_reference_views_migrate_deterministically():
    payload = _bible().to_dict()
    payload["schema_version"] = 1
    del payload["reference_views"][0]["view_type"]
    first = migrate_style_bible_payload(payload)
    second = migrate_style_bible_payload(payload)
    assert first == second
    assert first["reference_views"][0]["view_type"] == "other"
    assert CharacterStyleBible.from_dict(payload).reference_views[0].view_type == "other"


def test_reference_view_type_uses_controlled_vocabulary():
    with pytest.raises(ValueError, match="not supported"):
        ReferenceView("front", "Front", "references/front.png", view_type="hero-shot")


def test_schema_v1_migration_rejects_malformed_reference_entries():
    payload = _bible().to_dict()
    payload["schema_version"] = 1
    payload["reference_views"] = ["not-an-object"]
    with pytest.raises(ValueError, match="malformed"):
        migrate_style_bible_payload(payload)
