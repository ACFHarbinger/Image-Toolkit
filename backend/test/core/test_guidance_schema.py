"""#751: guidance schema, both hard validators, and the CI fixtures.

The known-broken payloads are built *from the live
`configs/comfy_workflows/` templates at test time* — fixtures can't rot
when the templates change, and schema adherence + the from-match rule are
CI-checkable without any live model call. The live-model test remains
only about answer quality.
"""
import json
from pathlib import Path

import pytest

from backend.src.core.guidance_schema import (
    SCHEMA_VERSION,
    GuidanceResponse,
    ModelSwap,
    ParamChange,
    SuggestionVerdict,
    Verdict,
    _coerce_equal,
    apply_validated,
    parse_guidance_response,
    validate_guidance,
    workflow_hash,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "configs" / "comfy_workflows"
TEMPLATE_NAMES = ("lora_generate.json", "controlnet_generate.json", "ipadapter_generate.json")


def _template(name):
    return json.loads((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


def _node_by_class(workflow, class_type):
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == class_type:
            return node_id, node["inputs"]
    raise AssertionError(f"template has no {class_type} node")


def _response(workflow, changes, swap=None, guidance=None, hash_override=None):
    return GuidanceResponse(
        schema_version=SCHEMA_VERSION,
        workflow_hash=hash_override or workflow_hash(workflow),
        workflow_param_changes=tuple(changes),
        model_swap=swap,
        dataset_guidance=guidance,
    )


# ---------------------------------------------------------------------------
# Fixtures over the live templates: known-broken variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_valid_suggestion_validates_and_applies(name, tmp_path):
    workflow = _template(name)
    node_id, inputs = _node_by_class(workflow, "KSampler")
    validation = validate_guidance(
        _response(workflow, [ParamChange(node_id, "steps", inputs["steps"], 30, "more steps")]),
        workflow,
    )
    assert validation.ok
    assert validation.valid_changes()
    patched = apply_validated(workflow, validation)
    assert patched is not None
    assert patched[node_id]["inputs"]["steps"] == 30
    # The original graph is untouched (deep copy, no shared state).
    assert workflow[node_id]["inputs"]["steps"] == inputs["steps"]


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_nonexistent_node_is_rejected(name):
    workflow = _template(name)
    node_id, inputs = _node_by_class(workflow, "KSampler")
    validation = validate_guidance(
        _response(workflow, [ParamChange("999", "steps", inputs["steps"], 30)]),
        workflow,
    )
    assert validation.verdicts[0].status == Verdict.INVALID_NODE
    assert apply_validated(workflow, validation) is None


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_nonexistent_input_is_rejected(name):
    workflow = _template(name)
    node_id, _inputs = _node_by_class(workflow, "KSampler")
    validation = validate_guidance(
        _response(workflow, [ParamChange(node_id, "no_such_input", 1, 2)]),
        workflow,
    )
    assert validation.verdicts[0].status == Verdict.INVALID_INPUT


def test_from_mismatch_flags_whole_response_not_silent_patch():
    workflow = _template("lora_generate.json")
    node_id, inputs = _node_by_class(workflow, "KSampler")
    real_cfg = inputs["cfg"]
    good = ParamChange(node_id, "steps", inputs["steps"], 30)
    bad = ParamChange(node_id, "cfg", float(real_cfg) + 1.0, 7.0)  # wrong premise
    validation = validate_guidance(_response(workflow, [good, bad]), workflow)
    assert validation.hallucination_flagged
    assert validation.verdicts[1].status == Verdict.FROM_MISMATCH
    assert "did not match" in validation.notes[0]
    # The whole batch is untrusted — even the valid row is not applied.
    assert apply_validated(workflow, validation) is None


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_out_of_range_cfg_is_rejected(name):
    workflow = _template(name)
    node_id, inputs = _node_by_class(workflow, "KSampler")
    validation = validate_guidance(
        _response(workflow, [ParamChange(node_id, "cfg", inputs["cfg"], 9999.0)]),
        workflow,
    )
    assert validation.verdicts[0].status == Verdict.OUT_OF_RANGE
    assert not validation.ok


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_model_swap_missing_asset_is_proposed_installation(name, tmp_path):
    workflow = _template(name)
    node_id, inputs = _node_by_class(workflow, "CheckpointLoaderSimple")
    swap = ModelSwap(node_id, "ckpt_name", inputs["ckpt_name"], "missing_model.safetensors", "better base")
    validation = validate_guidance(
        _response(workflow, [], swap=swap), workflow, models_root=tmp_path,
    )
    verdict = validation.verdicts[0]
    assert verdict.status == Verdict.MISSING_ASSET
    # Surfaced as an explicit proposed installation, never a silent apply.
    assert apply_validated(workflow, validation) is None

    # Installed asset swaps cleanly.
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "missing_model.safetensors").write_bytes(b"")
    validation = validate_guidance(
        _response(workflow, [], swap=swap), workflow, models_root=tmp_path,
    )
    assert validation.verdicts[0].status == Verdict.VALID
    patched = apply_validated(workflow, validation)
    assert patched[node_id]["inputs"]["ckpt_name"] == "missing_model.safetensors"


def test_stale_hash_rejects_everything():
    workflow = _template("lora_generate.json")
    node_id, inputs = _node_by_class(workflow, "KSampler")
    validation = validate_guidance(
        _response(workflow, [ParamChange(node_id, "steps", inputs["steps"], 30)],
                  hash_override="0" * 64),
        workflow,
    )
    assert validation.stale
    assert validation.verdicts[0].status == Verdict.STALE
    assert apply_validated(workflow, validation) is None


def test_partial_apply_of_valid_rows_only():
    workflow = _template("lora_generate.json")
    node_id, inputs = _node_by_class(workflow, "KSampler")
    good = ParamChange(node_id, "steps", inputs["steps"], 30)
    bad = ParamChange("404", "steps", 25, 30)  # nonexistent node row
    validation = validate_guidance(_response(workflow, [good, bad]), workflow)
    assert not validation.hallucination_flagged and not validation.stale
    patched = apply_validated(workflow, validation)
    assert patched is not None
    assert patched[node_id]["inputs"]["steps"] == 30
    assert "404" not in patched


# ---------------------------------------------------------------------------
# Parser: schema adherence, CI-checkable
# ---------------------------------------------------------------------------


def _raw_response(workflow, **overrides):
    node_id, inputs = _node_by_class(workflow, "KSampler")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "workflow_hash": workflow_hash(workflow),
        "workflow_param_changes": [
            {"node_id": node_id, "input": "steps", "from": inputs["steps"], "to": 30, "reason": "try more"}
        ],
        "model_swap": None,
        "dataset_guidance": None,
    }
    payload.update(overrides)
    return payload


def test_parse_dict_and_fenced_text():
    workflow = _template("lora_generate.json")
    node_id, _inputs = _node_by_class(workflow, "KSampler")

    parsed = parse_guidance_response(_raw_response(workflow))
    assert parsed.ok and parsed.response.workflow_param_changes[0].node_id == node_id

    fenced = "Here is my advice:\n```json\n" + json.dumps(_raw_response(workflow)) + "\n```\nThanks!"
    parsed = parse_guidance_response(fenced)
    assert parsed.ok
    assert parsed.response.workflow_param_changes[0].to_value == 30

    # Round-trip through the real validators.
    validation = validate_guidance(parsed.response, workflow)
    assert validation.ok


def test_parse_rejects_structural_violations():
    workflow = _template("lora_generate.json")
    assert not parse_guidance_response("not json at all").ok
    assert not parse_guidance_response("[1,2,3]").ok
    bad_version = _raw_response(workflow, schema_version=2)
    parsed = parse_guidance_response(bad_version)
    assert not parsed.ok and "schema_version" in parsed.errors[0]
    bad_hash = _raw_response(workflow, workflow_hash="short")
    assert not parse_guidance_response(bad_hash).ok
    bad_changes = _raw_response(workflow, workflow_param_changes=[{"node_id": "1"}])
    assert not parse_guidance_response(bad_changes).ok
    bad_swap = _raw_response(workflow, model_swap={"node_id": "1", "input": "ckpt_name", "from": "x"})
    assert not parse_guidance_response(bad_swap).ok


def test_parse_tolerates_unknown_keys_for_forward_compat():
    """#753 adds abstention/evidence fields on top of v1 — unknown keys
    must not break parsing."""
    workflow = _template("lora_generate.json")
    payload = _raw_response(workflow, abstention_reason="not enough signal", confidence=0.4)
    parsed = parse_guidance_response(payload)
    assert parsed.ok


def test_coerce_equal_type_rules():
    assert _coerce_equal("6.0", 6)
    assert _coerce_equal(6.0, 6)
    assert _coerce_equal("true", True)
    assert _coerce_equal(False, False)
    assert _coerce_equal('["1", 0]', ["1", 0])
    assert _coerce_equal("same", "same")
    assert not _coerce_equal("6", 7)
    assert _coerce_equal("yes", True)
    assert _coerce_equal("no", False)
    assert not _coerce_equal("junk", 6)
    assert not _coerce_equal("not-a-list", ["1", 0])


def test_verdict_valid_property():
    change = ParamChange("1", "steps", 25, 30)
    assert SuggestionVerdict(change, Verdict.VALID).valid
    assert not SuggestionVerdict(change, Verdict.INVALID_NODE).valid


def test_apply_rechecks_hash_after_validation():
    workflow = {"1": {"inputs": {"steps": 10}}}
    validation = validate_guidance(_response(workflow, [ParamChange("1", "steps", 10, 20)]), workflow)
    workflow["1"]["inputs"]["steps"] = 12
    assert apply_validated(workflow, validation) is None


@pytest.mark.parametrize("value", [2.5, True, float("nan"), {}, ["2", 0]])
def test_destination_cannot_change_scalar_type(value):
    workflow = {"1": {"inputs": {"steps": 10}}}
    validation = validate_guidance(_response(workflow, [ParamChange("1", "steps", 10, value)]), workflow)
    assert not validation.valid_changes()


def test_numeric_string_is_applied_as_integer():
    workflow = {"1": {"inputs": {"steps": 10}}}
    validation = validate_guidance(_response(workflow, [ParamChange("1", "steps", 10, "20")]), workflow)
    assert type(apply_validated(workflow, validation)["1"]["inputs"]["steps"]) is int


def test_duplicate_changes_are_rejected():
    workflow = {"1": {"inputs": {"steps": 10}}}
    changes = [ParamChange("1", "steps", 10, 20), ParamChange("1", "steps", 10, 30)]
    assert not validate_guidance(_response(workflow, changes), workflow).valid_changes()


def test_param_change_cannot_bypass_model_asset_check(tmp_path):
    folder = tmp_path / "checkpoints"
    folder.mkdir()
    (folder / "model.safetensors").touch()
    workflow = {"1": {"inputs": {"ckpt_name": "old.safetensors"}}}
    for target in ("missing/model.safetensors", "../model.safetensors"):
        change = ParamChange("1", "ckpt_name", "old.safetensors", target)
        validation = validate_guidance(_response(workflow, [change]), workflow, models_root=tmp_path)
        assert validation.verdicts[0].status == Verdict.MISSING_ASSET
        assert apply_validated(workflow, validation) is None


def test_sampler_name_is_not_a_model_asset():
    workflow = {"1": {"inputs": {"sampler_name": "euler"}}}
    change = ParamChange("1", "sampler_name", "euler", "dpmpp_2m")
    validation = validate_guidance(_response(workflow, [change]), workflow)
    assert apply_validated(workflow, validation)["1"]["inputs"]["sampler_name"] == "dpmpp_2m"


def test_seed_integer_precision_is_preserved():
    seed = 9007199254740993
    workflow = {"1": {"inputs": {"seed": seed}}}
    change = ParamChange("1", "seed", str(seed), str(seed + 2))
    validation = validate_guidance(_response(workflow, [change]), workflow)
    assert apply_validated(workflow, validation)["1"]["inputs"]["seed"] == seed + 2


def test_model_swap_uses_connected_server_asset_choices():
    workflow = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "old.safetensors"}}}
    info = {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["new.safetensors"]]}}}}
    response = _response(workflow, [], swap=ModelSwap("1", "ckpt_name", "old.safetensors", "new.safetensors"))
    validation = validate_guidance(response, workflow, object_info=info)
    assert apply_validated(workflow, validation)["1"]["inputs"]["ckpt_name"] == "new.safetensors"
