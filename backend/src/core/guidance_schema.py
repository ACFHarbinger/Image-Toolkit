"""Versioned guidance-response schema + validators (#751, Gate E.2).

The guidance advisor (OCR/VLM/LLM loop, #750) must return this schema,
not free text. Two hard validators run before anything is shown to the
user, both against the *executed* workflow JSON captured by #737's
/history provenance — never the model's reading of the workflow:

1. Existence — every referenced ``node_id``/``input`` must be real.
2. Premise — each claimed ``from`` must equal (type-coerced) the actual
   current value. A mismatch is hallucination evidence: the whole
   response is flagged, never silently patched.

Also enforced here: the response's echoed ``workflow_hash`` must match
the current graph (stale patches against a user-edited graph are
rejected), a ``model_swap`` target must be installed (or is surfaced as
an explicit proposed installation), and well-known numeric inputs get
conservative plausibility bounds.

``apply_validated`` is the only sanctioned way to turn suggestions into
a patch: it applies validated changes to a deep copy and refuses stale
or hallucination-flagged responses outright. ``ComfyUIManager.
apply_overrides``'s permissive unknown-node-ignoring behavior is never
the validation boundary.

Pure/torch-free on purpose: #752 (Diff & Apply) and #753 (evidence,
abstention) import this without touching the mocked models tree, and
schema adherence is CI-checkable without any live model call. Unknown
top-level keys are tolerated so #753 can extend v1.

#753's v1 extension (all optional, parsed tolerantly — malformed values
are dropped, never a parse failure): each change may carry ``evidence[]``
(:class:`EvidenceRef`) and a 0–1 ``confidence``; the response may carry
top-level ``needs[]`` (abstention: what to capture before re-trying) and
a free-text ``diagnosis``.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# Conservative plausibility bounds for well-known numeric inputs. A value
# outside these is an implausible suggestion (out-of-range CFG etc.),
# rejected before a human ever sees it.
NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "cfg": (0.0, 30.0),
    "steps": (1.0, 150.0),
    "denoise": (0.0, 1.0),
    "strength_model": (0.0, 2.0),
    "strength_clip": (0.0, 2.0),
    "batch_size": (1.0, 16.0),
    "width": (64.0, 8192.0),
    "height": (64.0, 8192.0),
}

# ComfyUI models/<family>/ folder for a swap input name.
_INPUT_FAMILY: tuple[tuple[str, str], ...] = (
    ("ckpt", "checkpoints"),
    ("checkpoint", "checkpoints"),
    ("lora", "loras"),
    ("vae", "vae"),
    ("control_net", "controlnet"),
    ("ipadapter", "ipadapter"),
    ("upscale", "upscale_models"),
    ("clip", "clip"),
    ("embedding", "embeddings"),
)


class Verdict:
    """Per-suggestion validation outcome."""

    VALID = "valid"
    INVALID_NODE = "invalid_node"
    INVALID_INPUT = "invalid_input"
    FROM_MISMATCH = "from_mismatch"
    OUT_OF_RANGE = "out_of_range"
    MISSING_ASSET = "missing_asset"
    STALE = "stale_hash"


@dataclass(frozen=True)
class EvidenceRef:
    """#753: one measured signal behind a suggestion.

    ``kind`` names the artifact family (``tournament``, ``advisor_finding``,
    ``run_record``, ``training_metric``, ``ocr``, ``vlm``); ``ref`` carries
    its ids (run_id, checkpoint key, finding id, …); ``summary`` is a
    one-liner the renderer shows — ``guidance_evidence.resolve`` replaces
    it with the real measured value when the artifact is on disk.
    """

    kind: str
    ref: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


@dataclass(frozen=True)
class ParamChange:
    node_id: str
    input_name: str  # wire key: "input"
    from_value: Any  # wire key: "from"
    to_value: Any  # wire key: "to"
    reason: str = ""
    # #753 extensions (optional in v1): what measured signals back this
    # change, and how confident the advisor is (0–1).
    evidence: tuple[EvidenceRef, ...] = ()
    confidence: float | None = None


@dataclass(frozen=True)
class ModelSwap:
    node_id: str
    input_name: str
    from_value: Any
    to_value: Any
    reason: str = ""
    evidence: tuple[EvidenceRef, ...] = ()
    confidence: float | None = None


@dataclass(frozen=True)
class GuidanceResponse:
    schema_version: int
    workflow_hash: str
    workflow_param_changes: tuple[ParamChange, ...] = ()
    model_swap: ModelSwap | None = None
    dataset_guidance: str | None = None
    # #753 abstention extension: what the advisor needs before it will
    # guess again. Non-empty needs with no actionable changes = the
    # first-class "insufficient evidence" output.
    needs: tuple[str, ...] = ()
    diagnosis: str | None = None


@dataclass(frozen=True)
class ParsedGuidance:
    ok: bool
    response: GuidanceResponse | None = None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SuggestionVerdict:
    change: ParamChange | ModelSwap
    status: str
    detail: str = ""

    @property
    def valid(self) -> bool:
        return self.status in (Verdict.VALID, Verdict.MISSING_ASSET)


@dataclass(frozen=True)
class GuidanceValidation:
    response: GuidanceResponse
    verdicts: tuple[SuggestionVerdict, ...] = ()
    stale: bool = False
    hallucination_flagged: bool = False
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.stale and not self.hallucination_flagged and bool(self.verdicts) and all(
            v.valid for v in self.verdicts
        )

    def valid_changes(self) -> tuple[ParamChange | ModelSwap, ...]:
        """Changes safe to show/apply (missing-asset swaps are shown as
        explicit proposed installations, not silently applied)."""
        return tuple(v.change for v in self.verdicts if v.status == Verdict.VALID)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def workflow_hash(workflow: Any) -> str:
    """Stable hash of the executed graph: canonical JSON → sha256."""
    canonical = json.dumps(workflow, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Parsing (never raises; schema adherence is CI-checkable)
# ---------------------------------------------------------------------------

def _extract_json(payload: str) -> str:
    """Pull the JSON object out of raw model output (fenced or prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = payload.find("{")
    end = payload.rfind("}")
    if 0 <= start < end:
        return payload[start : end + 1]
    return payload.strip()


def _evidence_refs(raw: Any) -> tuple[EvidenceRef, ...]:
    """#753: parse per-change evidence tolerantly — a malformed entry is
    dropped, never a reason to reject an otherwise-valid response (the
    hard failures live in the validators)."""
    if not isinstance(raw, list):
        return ()
    refs: list[EvidenceRef] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if not isinstance(kind, str) or not kind:
            continue
        ref = entry.get("ref") if isinstance(entry.get("ref"), dict) else {}
        summary = entry.get("summary", "")
        refs.append(
            EvidenceRef(
                kind=kind,
                ref=dict(ref),
                summary=summary if isinstance(summary, str) else str(summary),
            )
        )
    return tuple(refs)


def _confidence_value(raw: Any) -> float | None:
    """0–1 float or None; anything else is ignored, not an error."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and math.isfinite(raw):
        return max(0.0, min(1.0, float(raw)))
    return None


def _change(data: Any, errors: list[str], kind: type) -> Any | None:
    if not isinstance(data, dict):
        errors.append(f"{kind.__name__} entry is not an object")
        return None
    node_id = data.get("node_id")
    input_name = data.get("input")
    if not isinstance(node_id, str) or not node_id:
        errors.append(f"{kind.__name__} missing node_id")
        return None
    if not isinstance(input_name, str) or not input_name:
        errors.append(f"{kind.__name__} missing input")
        return None
    if "from" not in data or "to" not in data:
        errors.append(f"{kind.__name__} for {node_id}.{input_name} missing from/to")
        return None
    reason = data.get("reason", "")
    return kind(
        node_id=node_id,
        input_name=input_name,
        from_value=data["from"],
        to_value=data["to"],
        reason=reason if isinstance(reason, str) else str(reason),
        evidence=_evidence_refs(data.get("evidence")),
        confidence=_confidence_value(data.get("confidence")),
    )


def parse_guidance_response(payload: Any) -> ParsedGuidance:
    """Parse + structurally validate an advisor response (dict or raw
    model text). Returns errors instead of raising, so callers can show
    exactly what the model got wrong."""
    errors: list[str] = []
    data = payload
    if isinstance(payload, str):
        try:
            data = json.loads(_extract_json(payload))
        except json.JSONDecodeError as exc:
            return ParsedGuidance(ok=False, errors=(f"response is not JSON: {exc.msg}",))
    if not isinstance(data, dict):
        return ParsedGuidance(ok=False, errors=("response is not a JSON object",))

    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}, got {version!r}")

    wf_hash = data.get("workflow_hash")
    if not isinstance(wf_hash, str) or re.fullmatch(r"[0-9a-f]{64}", wf_hash) is None:
        errors.append("workflow_hash missing or not a sha256 hex digest")

    changes: list[ParamChange] = []
    raw_changes = data.get("workflow_param_changes")
    if not isinstance(raw_changes, list):
        errors.append("workflow_param_changes must be a list")
    else:
        for entry in raw_changes:
            change = _change(entry, errors, ParamChange)
            if change is not None:
                changes.append(change)

    swap = None
    raw_swap = data.get("model_swap")
    if raw_swap is not None:
        swap = _change(raw_swap, errors, ModelSwap)

    guidance = data.get("dataset_guidance")
    if guidance is not None and not isinstance(guidance, str):
        errors.append("dataset_guidance must be a string or null")

    # #753 abstention fields — parsed tolerantly like evidence; a
    # non-list ``needs`` is ignored rather than failing the response.
    raw_needs = data.get("needs")
    needs = (
        tuple(str(n) for n in raw_needs if isinstance(n, str) and str(n).strip())
        if isinstance(raw_needs, list)
        else ()
    )
    diagnosis = data.get("diagnosis")
    if diagnosis is not None and not isinstance(diagnosis, str):
        diagnosis = str(diagnosis)

    if errors:
        return ParsedGuidance(ok=False, errors=tuple(errors))
    return ParsedGuidance(
        ok=True,
        response=GuidanceResponse(
            schema_version=SCHEMA_VERSION,
            workflow_hash=wf_hash,
            workflow_param_changes=tuple(changes),
            model_swap=swap,
            dataset_guidance=guidance,
            needs=needs,
            diagnosis=diagnosis,
        ),
    )


# ---------------------------------------------------------------------------
# Validation against the executed workflow
# ---------------------------------------------------------------------------

def _coerce_equal(claimed: Any, current: Any) -> bool:
    """Type-coerced equality: numbers compare numerically, bools parse,
    link arrays via JSON, strings exactly."""
    if isinstance(current, bool) or isinstance(claimed, bool):
        return _as_bool(claimed) is current
    if isinstance(current, (int, float)):
        try:
            return Decimal(str(claimed)) == Decimal(str(current))
        except (TypeError, ValueError, InvalidOperation):
            return False
    if isinstance(current, (list, tuple)):
        try:
            return json.loads(claimed) == list(current) if isinstance(claimed, str) else list(claimed) == list(current)
        except (ValueError, TypeError):
            return False
    return str(claimed) == str(current)


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _model_family(input_name: str) -> str:
    lowered = input_name.lower()
    for marker, family in _INPUT_FAMILY:
        if marker in lowered:
            return family
    return "checkpoints"



def _is_asset_input(input_name: str) -> bool:
    return any(marker in input_name.lower() for marker, _family in _INPUT_FAMILY)


def _asset_installed(name: Any, family: str, models_root: Path | None) -> bool:
    if models_root is None or not isinstance(name, str) or not name:
        return False
    folder = Path(models_root) / family
    if not folder.is_dir():
        return False
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    return (folder / relative).is_file()



def _typed_destination(current: Any, proposed: Any) -> Any:
    if isinstance(current, bool):
        value = _as_bool(proposed)
        if value is None:
            raise ValueError("destination must be boolean")
        return value
    if isinstance(current, (int, float)):
        if isinstance(proposed, bool):
            raise ValueError("boolean is not a numeric destination")
        if isinstance(current, int):
            try:
                integer = Decimal(str(proposed))
                if not integer.is_finite() or integer != integer.to_integral_value():
                    raise ValueError("destination must be a finite integer")
                return int(integer)
            except InvalidOperation as exc:
                raise ValueError("destination must be an integer") from exc
        value = float(proposed)
        if not math.isfinite(value):
            raise ValueError("destination must be finite")
        return value
    if isinstance(current, str) and isinstance(proposed, str):
        return proposed
    raise ValueError("only scalar input changes are supported")



def _numeric_verdict(change: ParamChange | ModelSwap, destination: Any) -> SuggestionVerdict:
    bounds = NUMERIC_BOUNDS.get(change.input_name)
    if bounds is not None:
        try:
            value = float(destination)
        except (TypeError, ValueError, OverflowError):
            return SuggestionVerdict(change, Verdict.OUT_OF_RANGE, f"{change.input_name} must be numeric")
        if not bounds[0] <= value <= bounds[1]:
            return SuggestionVerdict(change, Verdict.OUT_OF_RANGE, f"{change.input_name}={value} outside {bounds}")
    return SuggestionVerdict(change, Verdict.VALID)



def _asset_available(change, node, models_root, object_info):
    if isinstance(object_info, dict):
        info = object_info.get(node.get("class_type"), {})
        inputs = info.get("input", {}) if isinstance(info, dict) else {}
        for section in ("required", "optional"):
            fields = inputs.get(section, {}) if isinstance(inputs, dict) else {}
            declaration = fields.get(change.input_name) if isinstance(fields, dict) else None
            if isinstance(declaration, (list, tuple)) and declaration and isinstance(declaration[0], list):
                return change.to_value in declaration[0]
    return _asset_installed(change.to_value, _model_family(change.input_name), models_root)


def validate_guidance(
    response: GuidanceResponse,
    workflow: Any,
    *,
    models_root: Path | str | None = None,
    object_info: dict | None = None,
) -> GuidanceValidation:
    """Run both hard validators + asset + bounds checks against the
    *executed* workflow graph. Nothing is trusted from the advisor."""
    notes: list[str] = []
    verdicts: list[SuggestionVerdict] = []
    stale = response.workflow_hash != workflow_hash(workflow)
    if stale:
        notes.append(
            "Workflow changed since the suggestion was generated; refusing to patch."
        )

    hallucination = False
    changes = response.workflow_param_changes + ((response.model_swap,) if response.model_swap else ())
    counts = Counter((c.node_id, c.input_name) for c in changes)

    def check(change: ParamChange | ModelSwap) -> SuggestionVerdict:
        nonlocal hallucination
        if stale:
            return SuggestionVerdict(change, Verdict.STALE, "workflow hash mismatch")
        node = workflow.get(change.node_id) if isinstance(workflow, dict) else None
        if not isinstance(node, dict):
            return SuggestionVerdict(change, Verdict.INVALID_NODE, f"node {change.node_id!r} not in the executed graph")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or change.input_name not in inputs:
            return SuggestionVerdict(
                change, Verdict.INVALID_INPUT, f"input {change.input_name!r} not on node {change.node_id}"
            )
        if counts[(change.node_id, change.input_name)] > 1:
            return SuggestionVerdict(change, Verdict.INVALID_INPUT, "duplicate input change")
        current = inputs[change.input_name]
        try:
            destination = _typed_destination(current, change.to_value)
        except (TypeError, ValueError, OverflowError) as exc:
            return SuggestionVerdict(change, Verdict.OUT_OF_RANGE, str(exc))
        if not _coerce_equal(change.from_value, current):
            hallucination = True
            return SuggestionVerdict(
                change,
                Verdict.FROM_MISMATCH,
                f"claimed from {change.from_value!r} but real value is {current!r}",
            )
        asset_input = isinstance(current, str) and _is_asset_input(change.input_name)
        if isinstance(change, ModelSwap) and not asset_input:
            return SuggestionVerdict(change, Verdict.INVALID_INPUT, "model swap requires a model-name input")
        if isinstance(change, ModelSwap) or asset_input:
            if not _asset_available(change, node, models_root, object_info):
                return SuggestionVerdict(
                    change,
                    Verdict.MISSING_ASSET,
                    f"{change.to_value!r} is not installed — proposed installation required",
                )
            return SuggestionVerdict(change, Verdict.VALID)
        return _numeric_verdict(change, destination)

    for change in response.workflow_param_changes:
        verdicts.append(check(change))
    if response.model_swap is not None:
        verdicts.append(check(response.model_swap))
    if hallucination:
        notes.append(
            "A suggestion's claimed current value did not match the workflow — "
            "treated as hallucination evidence; the whole response is flagged."
        )
    return GuidanceValidation(
        response=response,
        verdicts=tuple(verdicts),
        stale=stale,
        hallucination_flagged=hallucination,
        notes=tuple(notes),
    )


def apply_validated(
    workflow: Any,
    validation: GuidanceValidation,
) -> dict | None:
    """The only sanctioned patch path (#752 consumes this): apply the
    validated subset to a deep copy, per-row semantics. Refuses stale or
    hallucination-flagged responses outright — the whole batch is
    untrusted then, no silent partial application. Missing-asset model
    swaps never reach here (they are proposed installations, not applies).
    Returns None when there is nothing safe to apply."""
    if not isinstance(workflow, dict):
        return None
    if validation.stale or validation.hallucination_flagged or workflow_hash(workflow) != validation.response.workflow_hash:
        return None
    changes = validation.valid_changes()
    if not changes:
        return None
    patched = json.loads(json.dumps(workflow))  # deep copy, no shared state
    for change in changes:
        node = patched.get(change.node_id)
        if not isinstance(node, dict):
            return None
        inputs = node.setdefault("inputs", {})
        if change.input_name not in inputs:
            return None
        if not _coerce_equal(change.from_value, inputs[change.input_name]):
            return None
        try:
            inputs[change.input_name] = _typed_destination(inputs[change.input_name], change.to_value)
        except (TypeError, ValueError, OverflowError):
            return None
    return patched


__all__ = [
    "GuidanceResponse",
    "GuidanceValidation",
    "ModelSwap",
    "NUMERIC_BOUNDS",
    "ParamChange",
    "ParsedGuidance",
    "SCHEMA_VERSION",
    "SuggestionVerdict",
    "Verdict",
    "apply_validated",
    "parse_guidance_response",
    "validate_guidance",
    "workflow_hash",
]
