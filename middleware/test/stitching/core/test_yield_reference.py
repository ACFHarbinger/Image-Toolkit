"""refs #654: Ground-Rule #1 is exact under the deterministic protocol.

The unseeded 9-in/9-out full-97 pair is recorded as a noise floor, not as
an acceptance band.
"""

from __future__ import annotations

import json

from middleware.benchmark.asp.bootstrap import repo_root
from middleware.src.stitching.core.pipeline.yield_reference import (
    EXACT_DETERMINISTIC_BAND,
    REFERENCE_PROTOCOL_ENV,
    UNSEEDED_FULL97_20260917_BAND,
    UNSEEDED_RAW_ASP_GAINED,
    UNSEEDED_RAW_ASP_LOST,
    VERIFY_DATASETS,
    CaseOutcome,
    compare_outcomes,
    compare_run_files,
    main,
    outcomes_from_run_document,
    reference_status,
    within_band,
)


def _raw(name: str) -> CaseOutcome:
    return CaseOutcome(name, "raw_asp", None)


def _scans(name: str, reason: str) -> CaseOutcome:
    return CaseOutcome(name, "scans", reason)


def test_unseeded_full97_swap_is_not_a_deterministic_reference():
    reference = {name: _raw(name) for name in UNSEEDED_RAW_ASP_LOST}
    reference.update({name: _scans(name, "no_valid_edges") for name in UNSEEDED_RAW_ASP_GAINED})
    rerun = {name: _scans(name, "seam_vis_gate:asp=53.7") for name in UNSEEDED_RAW_ASP_LOST}
    rerun.update({name: _raw(name) for name in UNSEEDED_RAW_ASP_GAINED})
    comparison = compare_outcomes(reference, rerun)
    assert comparison.raw_asp_count_delta == 0
    assert comparison.raw_asp_symmetric_difference == 18
    assert comparison.gained_raw_asp == UNSEEDED_RAW_ASP_GAINED
    assert comparison.lost_raw_asp == UNSEEDED_RAW_ASP_LOST
    status = reference_status(comparison)
    assert status.exact is False
    assert status.matches_unseeded_noise_floor is True
    assert status.accept_as_deterministic_reference is False
    assert within_band(comparison, EXACT_DETERMINISTIC_BAND) is False
    assert within_band(comparison, UNSEEDED_FULL97_20260917_BAND) is True


def test_gate_family_change_fails_the_exact_band():
    # asp_test22 in the #654 note: same non-RAW outcome, different gate.
    before = {"asp_test22": _scans("asp_test22", "affine_invalid:min_gap=22.7px")}
    after = {"asp_test22": _scans("asp_test22", "seam_vis_gate:asp=53.7")}
    comparison = compare_outcomes(before, after)
    assert comparison.raw_asp_symmetric_difference == 0
    assert comparison.gate_prefix_changes == ("asp_test22",)
    assert reference_status(comparison).accept_as_deterministic_reference is False


def test_identical_fallback_strings_are_an_exact_reference():
    reason = "seam_vis_gate:asp=108.5_sim=6.9_limit=35.0"
    rows = {
        "asp_test31": _scans("asp_test31", reason),
        "asp_test09": _raw("asp_test09"),
    }
    status = reference_status(compare_outcomes(rows, dict(rows)))
    assert status.exact is True
    assert status.accept_as_deterministic_reference is True


def test_count_delta_is_outside_the_unseeded_full97_floor():
    # The same-day rerun flipped 3 of 9 "lost" cases back to RAW_ASP.
    # That moves the count, so it is not inside the tied-count noise floor.
    lost = UNSEEDED_RAW_ASP_LOST
    first = {name: _scans(name, "seam_vis_gate:asp=1") for name in lost}
    second = dict(first)
    for name in lost[:3]:
        second[name] = _raw(name)
    comparison = compare_outcomes(first, second)
    assert comparison.raw_asp_count_delta == 3
    assert reference_status(comparison).matches_unseeded_noise_floor is False
    assert reference_status(comparison).exact is False


def test_run_document_round_trip(tmp_path):
    doc = {
        "datasets": [
            {
                "name": "asp_test09",
                "result_identity": "raw_asp",
                "fallback_reason": None,
            },
            {
                "name": "asp_test31",
                "result_identity": "scans",
                "fallback_reason": "seam_vis_gate:asp=108.5_sim=6.9_limit=35.0",
            },
        ]
    }
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text(json.dumps(doc), encoding="utf-8")
    path_b.write_text(json.dumps({"results": doc["datasets"]}), encoding="utf-8")
    assert outcomes_from_run_document(doc["datasets"])["asp_test09"].raw_asp
    comparison, status = compare_run_files(path_a, path_b)
    assert status.accept_as_deterministic_reference is True
    assert comparison.n_shared == 2
    assert main([str(path_a), str(path_b)]) == 0
    drifted = dict(doc)
    drifted["datasets"] = [
        doc["datasets"][0],
        {
            "name": "asp_test31",
            "result_identity": "scans",
            "fallback_reason": "composite_gate_sb:asp_sc=30.2",
        },
    ]
    path_c = tmp_path / "c.json"
    path_c.write_text(json.dumps(drifted), encoding="utf-8")
    assert main([str(path_a), str(path_c)]) == 1


def test_benchmark_recipe_defaults_match_the_reference_protocol():
    text = (repo_root() / "tools" / "benchmark" / "justfile").read_text(encoding="utf-8")
    for key, value in REFERENCE_PROTOCOL_ENV.items():
        # justfile escapes the quotes: ASP_DETERMINISTIC=\"${ASP_DETERMINISTIC:-1}\"
        assert f"${{{key}:-{value}}}" in text
    verify = text.split("asp-benchmark-verify:", 1)[1].split("\nasp-benchmark-clean:", 1)[0]
    for name in VERIFY_DATASETS:
        assert name in verify
    assert len(VERIFY_DATASETS) == 5
