"""Provenance-bound parent/variant pair identity (#754 hold)."""
import os
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.src.core.guidance_pair import (
    BoundPair,
    PairLoadError,
    contained_path,
    first_image_spec,
    identity_error,
    load_comparison_pair,
    pair_files_alive,
    pair_ids_from_trajectory,
    pair_matches_trajectory,
    persist_verdict,
)
from backend.src.core.guidance_trajectory import (
    AppliedChange,
    GuidanceTrajectory,
    TrajectoryStep,
    append_step,
)
from backend.src.models.core.comfy_provenance import OutputRef


def _record(prompt_id, *, parent=None, path="", outputs=(), label=None):
    return SimpleNamespace(
        prompt_id=prompt_id,
        parent_prompt_id=parent,
        local_output_path=path,
        outputs=outputs,
        variant_label=label,
    )


def _traj(parent="p0", variant="v1"):
    return append_step(
        GuidanceTrajectory(root_prompt_id=parent),
        TrajectoryStep(
            parent_prompt_id=parent,
            variant_prompt_id=variant,
            applied=(AppliedChange("6", "cfg", 8.5, 6.0),),
        ),
    )


def test_pair_ids_require_both_prompt_ids():
    assert pair_ids_from_trajectory(None) is None
    empty = GuidanceTrajectory(root_prompt_id="p0")
    assert pair_ids_from_trajectory(empty) is None
    refs = pair_ids_from_trajectory(_traj())
    assert refs.parent_prompt_id == "p0"
    assert refs.variant_prompt_id == "v1"


def test_identity_rejects_unrelated_or_unlinked_records():
    parent = _record("p0")
    variant = _record("v1", parent="p0")
    assert identity_error(parent, variant, expected_parent="p0", expected_variant="v1") is None
    assert identity_error(None, variant, expected_parent="p0", expected_variant="v1")
    assert identity_error(parent, _record("other", parent="p0"), expected_parent="p0", expected_variant="v1")
    assert identity_error(parent, _record("v1", parent="other"), expected_parent="p0", expected_variant="v1")


def test_first_image_spec_prefers_local_then_image_output():
    local = _record("p0", path="/tmp/a.png")
    assert first_image_spec(local).local_path == "/tmp/a.png"
    remote = _record(
        "p0",
        outputs=(OutputRef(node_id="9", kind="images", filename="out.png", type="output"),),
    )
    spec = first_image_spec(remote)
    assert spec.filename == "out.png"
    assert spec.kind == "output"
    assert first_image_spec(_record("p0", outputs=())) is None


def test_contained_path_refuses_escape(tmp_path):
    assert contained_path(tmp_path, "v1", "out.png").parent == tmp_path / "v1"
    nested = contained_path(tmp_path, "..", "etc")
    assert nested is not None
    assert tmp_path.resolve() in nested.resolve().parents or nested.resolve() == tmp_path.resolve()


def test_load_comparison_pair_uses_existing_local_files(tmp_path):
    parent_file = tmp_path / "parent.png"
    variant_file = tmp_path / "variant.png"
    Image.new("RGB", (4, 4)).save(parent_file)
    Image.new("RGB", (4, 4)).save(variant_file)
    pair = load_comparison_pair(
        parent_record=_record("p0", path=str(parent_file)),
        variant_record=_record("v1", parent="p0", path=str(variant_file)),
        expected_parent="p0",
        expected_variant="v1",
        cache_dir=tmp_path / "cache",
        generation=3,
    )
    assert pair.paths == [str(parent_file), str(variant_file)]
    assert pair.generation == 3
    assert pair_files_alive(pair)
    assert pair_matches_trajectory(pair, _traj())


def test_load_comparison_pair_fetches_missing_remote(tmp_path):
    fetched = []

    def fetch(filename, subfolder, kind):
        fetched.append((filename, subfolder, kind))
        image = BytesIO()
        Image.new("RGB", (4, 4)).save(image, format="PNG")
        return image.getvalue()

    pair = load_comparison_pair(
        parent_record=_record(
            "p0",
            outputs=(OutputRef(node_id="9", kind="images", filename="base.png"),),
        ),
        variant_record=_record(
            "v1",
            parent="p0",
            outputs=(OutputRef(node_id="9", kind="images", filename="var.png", subfolder="x"),),
        ),
        expected_parent="p0",
        expected_variant="v1",
        cache_dir=tmp_path,
        fetch=fetch,
        exists=lambda path: os.path.isfile(path),
        generation=1,
    )
    assert fetched == [("base.png", "", "output"), ("var.png", "x", "output")]
    assert os.path.isfile(pair.parent_path)
    assert os.path.isfile(pair.variant_path)
    assert pair.parent_path.startswith(str(tmp_path))


def test_load_comparison_pair_refuses_identity_mismatch(tmp_path):
    with pytest.raises(PairLoadError, match="parent mismatch"):
        load_comparison_pair(
            parent_record=_record("p0", path=str(tmp_path / "a.png")),
            variant_record=_record("v1", parent="nope", path=str(tmp_path / "b.png")),
            expected_parent="p0",
            expected_variant="v1",
            cache_dir=tmp_path,
            generation=1,
        )


def test_stale_generation_does_not_match_later_bind():
    bound = BoundPair("p0", "v1", "/a.png", "/b.png", generation=1)
    assert not pair_matches_trajectory(bound, _traj("p0", "v2"))


def test_persist_verdict_updates_record_and_sidecar():
    written = []
    sidecars = []

    class Manager:
        def update_run_meta(self, prompt_id, meta):
            written.append((prompt_id, meta))

    traj = _traj()
    persist_verdict(Manager(), traj, "v1", sidecars.append)
    assert written[0][0] == "v1"
    assert written[0][1]["guidance_trajectory"]["root_prompt_id"] == "p0"
    assert sidecars == [traj]


def test_unknown_selected_variant_cannot_fall_back_to_latest():
    assert pair_ids_from_trajectory(_traj(), "not-in-history") is None


def test_cache_identity_includes_unsanitized_ids_and_output_fields(tmp_path):
    from backend.src.core.guidance_pair import OutputSpec, materialize_output

    specs = [
        OutputSpec("a/b", None, "out.png", "folder", "output"),
        OutputSpec("a_b", None, "out.png", "folder", "output"),
        OutputSpec("a_b", None, "out.png", "another", "output"),
        OutputSpec("a_b", None, "out.png", "another", "temp"),
    ]
    paths = [materialize_output(spec, cache_dir=tmp_path, fetch=lambda *_: b"x") for spec in specs]
    assert len(set(paths)) == len(specs)


def test_corrupt_outputs_cannot_enable_comparison(tmp_path):
    path = tmp_path / "not-an-image.png"
    path.write_text("upstream error")
    with pytest.raises(PairLoadError, match="unreadable"):
        load_comparison_pair(
            parent_record=_record("p", path=str(path)),
            variant_record=_record("v", parent="p", path=str(path)),
            expected_parent="p", expected_variant="v", cache_dir=tmp_path, generation=1,
        )
