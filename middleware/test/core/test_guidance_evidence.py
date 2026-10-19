"""#753: evidence resolution + confidence calibration (pure)."""

import pytest

from middleware.src.core import checkpoint_tournament
from middleware.src.core import guidance_evidence as ge
from middleware.src.core.guidance_schema import (
    EvidenceRef,
    parse_guidance_response,
    validate_guidance,
    workflow_hash,
)
from middleware.src.core.training_runs import start_run

WF = {"n1": {"class_type": "KSampler", "inputs": {"cfg": 8.5}}}  # ComfyUI prompt-API shape
WF_HASH = workflow_hash(WF)


def _response_payload(**change_over):
    change = {
        "node_id": "n1",
        "input": "cfg",
        "from": 8.5,
        "to": 6.0,
        "reason": "lower for this model",
    }
    change.update(change_over)
    return {
        "schema_version": 1,
        "workflow_hash": WF_HASH,
        "workflow_param_changes": [change],
    }


# ---------------------------------------------------------------------------
# Schema extension parsing
# ---------------------------------------------------------------------------

def test_parse_change_evidence_and_confidence():
    parsed = parse_guidance_response(
        _response_payload(
            confidence=0.85,
            evidence=[{"kind": "tournament", "ref": {"run_id": "r1"}, "summary": "s"}],
        )
    )
    assert parsed.ok, parsed.errors
    change = parsed.response.workflow_param_changes[0]
    assert change.confidence == pytest.approx(0.85)
    assert len(change.evidence) == 1
    assert change.evidence[0].kind == "tournament"
    assert change.evidence[0].ref == {"run_id": "r1"}


def test_parse_malformed_evidence_is_dropped_not_fatal():
    parsed = parse_guidance_response(
        _response_payload(evidence=[{"nope": 1}, "junk", {"kind": "tournament"}])
    )
    assert parsed.ok, parsed.errors
    change = parsed.response.workflow_param_changes[0]
    assert len(change.evidence) == 1  # only the kind-bearing entry survives
    assert change.evidence[0].ref == {}


def test_parse_confidence_clamped_and_garbage_ignored():
    parsed = parse_guidance_response(_response_payload(confidence=1.7))
    assert parsed.ok and parsed.response.workflow_param_changes[0].confidence == 1.0
    parsed = parse_guidance_response(_response_payload(confidence="high"))
    assert parsed.ok and parsed.response.workflow_param_changes[0].confidence is None


def test_parse_abstention_fields():
    payload = _response_payload()
    payload["workflow_param_changes"] = []
    payload["needs"] = ["more hand-angle variety", 42, "  "]
    payload["diagnosis"] = "OCR and VLM disagree"
    parsed = parse_guidance_response(payload)
    assert parsed.ok, parsed.errors
    assert parsed.response.needs == ("more hand-angle variety",)
    assert parsed.response.diagnosis == "OCR and VLM disagree"


def test_parse_needs_non_list_is_ignored():
    payload = _response_payload()
    payload["needs"] = "more variety"
    parsed = parse_guidance_response(payload)
    assert parsed.ok and parsed.response.needs == ()


# ---------------------------------------------------------------------------
# Confidence rubric (Qwen §5.3, made literal)
# ---------------------------------------------------------------------------

def test_band_thresholds():
    assert ge.confidence_band(0.85).name == "high"
    assert ge.confidence_band(0.8).name == "high"
    assert ge.confidence_band(0.6).name == "medium"
    assert ge.confidence_band(0.5).name == "medium"
    assert ge.confidence_band(0.49).name == "low"
    assert ge.confidence_band(0.0).name == "low"
    assert ge.confidence_band(0.0).hint  # low carries the abstention hint


def test_confidence_base_and_verified_premise():
    assert ge.compute_confidence() == pytest.approx(0.5)
    assert ge.compute_confidence(verified=True) == pytest.approx(0.7)
    assert ge.compute_confidence(verified=False) == pytest.approx(0.3)


def test_confidence_agreeing_signals_capped():
    ev = tuple(
        EvidenceRef(kind=k, ref={}) for k in ("tournament", "ocr", "vlm", "run_record", "advisor_finding")
    )
    score = ge.compute_confidence(verified=True, evidence=ev)
    # +0.2 verified +0.3 cap (5 kinds → 4 beyond first, capped at 3)
    assert score == pytest.approx(1.0)


def test_confidence_contradiction_lowers():
    agree = (EvidenceRef(kind="ocr", ref={}), EvidenceRef(kind="vlm", ref={}))
    contradicting = agree + (EvidenceRef(kind="vlm", ref={"polarity": "contradicts"}),)
    assert ge.compute_confidence(verified=True, evidence=contradicting) < ge.compute_confidence(
        verified=True, evidence=agree
    )
    assert ge.count_contradictions(contradicting) == 1


def test_confidence_flagged_caps_below_medium():
    assert ge.compute_confidence(verified=True, advisor_score=0.95, flagged=True) < 0.5


def test_advisor_score_is_a_prior_not_a_verdict():
    derived = ge.compute_confidence(verified=False, advisor_score=0.9)
    assert derived < 0.5  # unverified premise stays low even if advisor was sure
    derived_ok = ge.compute_confidence(verified=True, advisor_score=0.9)
    assert 0.7 < derived_ok < 0.9


def _validated(**change_over):
    parsed = parse_guidance_response(_response_payload(**change_over))
    return parsed.response.workflow_param_changes[0], validate_guidance(
        parsed.response, WF
    )


def test_confidence_for_change_reads_validation():
    change, validation = _validated(confidence=0.9)
    score = ge.confidence_for_change(change, validation)
    # Advisor self-confidence is not corroborating evidence:
    # honestly medium, not high (Qwen's rubric reserves high for agreement).
    assert score == pytest.approx(0.7)
    assert ge.confidence_band(score).name == "medium"


def test_confidence_for_change_premise_failure_stays_low():
    change, validation = _validated(**{"from": 3.0, "confidence": 0.9})
    score = ge.confidence_for_change(change, validation)
    assert score < 0.5  # hallucinated from-value: never present as trustworthy


def test_confidence_for_change_flagged_batch_capped():
    change, validation = _validated(confidence=0.95)
    flagged = type(validation)(
        response=validation.response,
        verdicts=validation.verdicts,
        stale=True,
    )
    assert ge.confidence_for_change(change, flagged) < 0.5


# ---------------------------------------------------------------------------
# Evidence resolution
# ---------------------------------------------------------------------------

@pytest.fixture
def run_with_tournament(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "lora.safetensors").write_bytes(b"")
    run_dir = tmp_path / "20261012-120000-demo-cafef00d"
    start_run(
        runs_root=tmp_path,
        run_id=run_dir.name,
        output_name="demo",
        engine="v2",
        model_id="fake/model",
        trigger_word="zxc",
        lora_path=str(out / "lora.safetensors"),
        config={"output_dir": str(out)},
    )
    state = checkpoint_tournament.TournamentState(run_id=run_dir.name)
    for key in ("epoch-0000", "epoch-0001"):
        state.entries[key] = checkpoint_tournament.TournamentEntry(
            key=key, label=key.replace("-", " "), checkpoint_path=str(out), sample_path=str(out / "lora.safetensors")
        )
    checkpoint_tournament.record_result(state, "epoch-0000", "epoch-0001", "a", ts=1.0)
    checkpoint_tournament.promote(state, "epoch-0000", ts=2.0)
    checkpoint_tournament.save_state(run_dir, state)
    return run_dir


def test_resolve_tournament_reads_real_state(run_with_tournament):
    ref = EvidenceRef(kind="tournament", ref={"run_id": run_with_tournament.name})
    resolved = ge.resolve_evidence(ref, runs_root=run_with_tournament.parent)
    assert not resolved.stale
    assert "epoch 0000" in resolved.title
    assert "ELO" in resolved.title
    assert resolved.target_dir == str(run_with_tournament)


def test_resolve_tournament_missing_is_stale(tmp_path):
    ref = EvidenceRef(kind="tournament", ref={"run_id": "nope"}, summary="advisor said")
    resolved = ge.resolve_evidence(ref, runs_root=tmp_path)
    assert resolved.stale
    assert "tournament.json" in resolved.detail


def test_resolve_run_record(tmp_path):
    run_dir = tmp_path / "20261012-130000-x-12345678"
    start_run(
        runs_root=tmp_path,
        run_id=run_dir.name,
        output_name="x",
        engine="v1",
        model_id="m",
        trigger_word="abc",
    )
    resolved = ge.resolve_evidence(
        EvidenceRef(kind="run_record", ref={"run_id": run_dir.name}), runs_root=tmp_path
    )
    assert not resolved.stale
    assert "abc" in resolved.title
    assert resolved.target_dir == str(run_dir)


def test_resolve_advisor_paths_existence_checked(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    ref = EvidenceRef(
        kind="advisor_finding",
        ref={"category": "near_duplicates", "paths": [str(img), str(tmp_path / "gone.png")]},
        summary="cluster of 12",
    )
    resolved = ge.resolve_evidence(ref)
    assert not resolved.stale
    assert resolved.paths == (str(img),)
    assert "near_duplicates" in resolved.title

    missing = ge.resolve_evidence(
        EvidenceRef(kind="advisor_finding", ref={"paths": [str(tmp_path / "gone.png")]})
    )
    assert missing.stale


def test_resolve_model_signals_are_summary_only():
    ocr = ge.resolve_evidence(EvidenceRef(kind="ocr", ref={}, summary="text reads 'cfg 8.5'"))
    assert "OCR" in ocr.title and not ocr.stale
    vlm = ge.resolve_evidence(EvidenceRef(kind="vlm", ref={}, summary="hands malformed"))
    assert "VLM" in vlm.title
    metric = ge.resolve_evidence(EvidenceRef(kind="training_metric", ref={}, summary="plateau at step 40"))
    assert metric.title == "plateau at step 40"


def test_gather_run_evidence(run_with_tournament):
    refs = ge.gather_run_evidence(run_with_tournament)
    kinds = [r.kind for r in refs]
    assert kinds.count("run_record") == 1
    assert kinds.count("tournament") == 2  # overall + promoted
    assert any(r.ref.get("checkpoint") == "epoch-0000" for r in refs)


def test_gather_run_evidence_without_record(tmp_path):
    assert ge.gather_run_evidence(tmp_path / "empty") == ()


def test_needs_pick_list(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    needs = ("more variety",)
    refs = (
        EvidenceRef(kind="advisor_finding", ref={"paths": [str(img), str(img)]}),
        EvidenceRef(kind="advisor_finding", ref={"paths": [str(tmp_path / "no.png")]}),
    )
    assert ge.needs_pick_list(needs, refs) == (str(img),)
    assert ge.needs_pick_list((), refs) == ()


def test_invented_evidence_cannot_raise_confidence():
    from dataclasses import replace

    change, validation = _validated()
    fake = replace(change, confidence=1.0,
                   evidence=tuple(EvidenceRef(kind=k) for k in ("madeup", "vlm", "ocr", "training_metric")))
    assert ge.confidence_for_change(fake, validation) == ge.confidence_for_change(change, validation)


def test_evidence_paths_do_not_import_directories_or_iterate_strings(tmp_path):
    ref = EvidenceRef(kind="advisor_finding", ref={"paths": str(tmp_path)})
    assert ge.needs_pick_list(("more",), (ref,)) == ()
    ref = EvidenceRef(kind="advisor_finding", ref={"paths": [str(tmp_path)]})
    assert ge.needs_pick_list(("more",), (ref,)) == ()


def test_missing_checkpoint_does_not_silently_resolve_to_leader(run_with_tournament):
    result = ge.resolve_evidence(
        EvidenceRef(kind="tournament", ref={"run_id": run_with_tournament.name, "checkpoint": "missing"}),
        runs_root=run_with_tournament.parent,
    )
    assert result.stale


def test_run_reference_cannot_escape_runs_root(tmp_path):
    result = ge.resolve_evidence(EvidenceRef(kind="run_record", ref={"run_id": "../elsewhere"}), runs_root=tmp_path)
    assert result.stale and not result.target_dir
