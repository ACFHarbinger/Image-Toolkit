"""Tests for §3.16B HITL per-test preset system."""

from backend.src.animation.hitl_presets import (
    HitlPreset,
    load_hitl_preset,
    save_hitl_preset,
    apply_hitl_preset,
    list_hitl_presets,
)


class TestHitlPreset:
    def test_round_trip(self, tmp_path):
        p = HitlPreset(
            test_name="test09",
            drop_edges=[(0, 1), (2, 3)],
            forced_boundaries=[300, 600],
            notes="manual fix",
        )
        save_hitl_preset("test09", p, base_dir=str(tmp_path))
        loaded = load_hitl_preset("test09", base_dir=str(tmp_path))
        assert loaded is not None
        assert loaded.drop_edges == [(0, 1), (2, 3)]
        assert loaded.forced_boundaries == [300, 600]
        assert loaded.notes == "manual fix"

    def test_load_missing_returns_none(self, tmp_path):
        assert load_hitl_preset("nonexistent", base_dir=str(tmp_path)) is None

    def test_list_presets(self, tmp_path):
        save_hitl_preset(
            "test09", HitlPreset(test_name="test09"), base_dir=str(tmp_path)
        )
        save_hitl_preset(
            "test27", HitlPreset(test_name="test27"), base_dir=str(tmp_path)
        )
        names = list_hitl_presets(base_dir=str(tmp_path))
        assert names == ["test09", "test27"]

    def test_apply_drop_edges(self):
        state = {
            "edges": [
                {"src": 0, "dst": 1, "w": 0.9},
                {"src": 1, "dst": 2, "w": 0.8},
            ]
        }
        preset = HitlPreset(test_name="t", drop_edges=[(0, 1)])
        apply_hitl_preset(state, preset)
        assert len(state["edges"]) == 1
        assert state["edges"][0]["src"] == 1

    def test_apply_force_scans(self):
        state = {}
        preset = HitlPreset(test_name="t", force_scans=True)
        apply_hitl_preset(state, preset)
        assert state["force_scans"] is True
