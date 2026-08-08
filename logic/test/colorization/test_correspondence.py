import itertools
import json
import os

import pytest

from colorization.correspondence import (
    CorrespondenceSet,
    RegionCorrespondence,
    load_correspondence_set,
    migrate_correspondence_payload,
    save_correspondence_set,
)


def _set():
    return CorrespondenceSet(
        "aiko-page-1",
        "aiko-tv",
        [
            RegionCorrespondence("r1", "hair-front-large", "hair", "local"),
            RegionCorrespondence("r2", "skin-face", "skin", "local", panel_id="panel-1"),
        ],
    )


def _counter():
    counter = itertools.count(1)
    return lambda: f"r{next(counter) + 100}"


def test_round_trip_uses_canonical_json_and_excludes_pixels(tmp_path):
    path = save_correspondence_set(tmp_path / "correspondence/aiko.json", _set())
    assert load_correspondence_set(path) == _set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["correspondences"][0]["material_id"] == "hair"
    assert "pixels" not in payload


def test_save_rotates_last_valid_set_into_bounded_recovery(tmp_path):
    path = tmp_path / "aiko.json"
    save_correspondence_set(path, _set())
    changed = _set()
    changed.correspondences.append(RegionCorrespondence("r3", "eyes-iris", "eyes"))
    save_correspondence_set(path, changed)
    recovered = load_correspondence_set(tmp_path / ".recovery/aiko.1.json")
    assert len(recovered.correspondences) == 2
    assert len(load_correspondence_set(path).correspondences) == 3


def test_interrupted_replace_preserves_last_valid_set(tmp_path, monkeypatch):
    path = tmp_path / "aiko.json"
    save_correspondence_set(path, _set())
    changed = _set()
    changed.correspondences.append(RegionCorrespondence("r3", "eyes-iris", "eyes"))
    monkeypatch.setattr(
        os, "replace", lambda source, destination: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(OSError, match="disk"):
        save_correspondence_set(path, changed)
    assert len(load_correspondence_set(path).correspondences) == 2


def test_competing_region_assignment_is_rejected():
    corr = _set()
    corr.correspondences.append(RegionCorrespondence("r3", "hair-front-large", "skin"))
    with pytest.raises(ValueError, match="competing materials"):
        corr.validate()


def test_same_region_in_different_panels_is_not_a_conflict():
    corr = _set()
    corr.correspondences.append(
        RegionCorrespondence("r3", "hair-front-large", "hair", panel_id="panel-2")
    )
    corr.validate()


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError, match="not supported"):
        RegionCorrespondence("r1", "hair-front-large", "hair", role="rim-light")


def test_unknown_or_future_schema_is_rejected():
    payload = _set().to_dict()
    payload["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported"):
        CorrespondenceSet.from_dict(payload)
    payload = _set().to_dict() | {"embedding": [1, 2, 3]}
    with pytest.raises(ValueError, match="unknown fields"):
        CorrespondenceSet.from_dict(payload)


def test_migrate_rejects_non_current_versions():
    payload = _set().to_dict()
    payload["schema_version"] = 0
    with pytest.raises(ValueError, match="unsupported"):
        migrate_correspondence_payload(payload)


def test_propagate_applies_to_explicit_targets_only():
    corr = _set()
    propagated = corr.propagate("r1", ["hair-back-large", "hair-bangs"], _counter())
    assigned = {item.region_id: item.material_id for item in propagated.correspondences}
    assert assigned["hair-back-large"] == "hair"
    assert assigned["hair-bangs"] == "hair"
    assert len(propagated.correspondences) == len(corr.correspondences) + 2


def test_propagate_refuses_to_overwrite_competing_assignment():
    corr = _set()
    corr.correspondences.append(RegionCorrespondence("r3", "eyes-iris", "eyes"))
    with pytest.raises(ValueError, match="competing assignment"):
        corr.propagate("r1", ["eyes-iris"], _counter())


def test_propagate_is_idempotent_for_already_matching_targets():
    corr = _set()
    once = corr.propagate("r1", ["hair-back-large"], _counter())
    twice = once.propagate("r1", ["hair-back-large"], _counter())
    assert once == twice


def test_propagate_requires_existing_source_and_explicit_targets():
    corr = _set()
    with pytest.raises(ValueError, match="does not exist"):
        corr.propagate("missing", ["hair-back-large"], _counter())
    with pytest.raises(ValueError, match="at least one"):
        corr.propagate("r1", [], _counter())
