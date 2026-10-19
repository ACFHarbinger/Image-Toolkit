"""Preflight scans: ComfyUI widget secrets and weight cloud-classes (#831)."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterator, List, Mapping, Sequence, Tuple

REDACTED = "«redacted»"

_SECRET_KEYS = re.compile(r"(api[_-]?key|token|secret|password|passwd|auth|bearer|credential)", re.I)
_SECRET_VALUES = [
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}", re.I)),
    ("credentials in URL", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.I)),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


@dataclass(frozen=True)
class SecretFinding:
    node_id: str
    field: str
    reason: str


def _iter_widgets(workflow: Mapping[str, Any]) -> Iterator[Tuple[str, str, Any]]:
    """API-format graphs: {node_id: {"inputs": {...}}}; UI-format: {"nodes": [{"id", "widgets_values"}]}."""
    if isinstance(workflow.get("nodes"), list):
        for node in workflow["nodes"]:
            for i, v in enumerate(node.get("widgets_values") or []):
                yield str(node.get("id")), f"widgets_values[{i}]", v
        return
    for node_id, node in workflow.items():
        if isinstance(node, Mapping):
            for key, value in (node.get("inputs") or {}).items():
                yield str(node_id), key, value


def scan_workflow_secrets(workflow: Mapping[str, Any]) -> List[SecretFinding]:
    found: List[SecretFinding] = []
    for node_id, key, value in _iter_widgets(workflow):
        if not isinstance(value, str) or not value:
            continue
        for label, pattern in _SECRET_VALUES:
            if pattern.search(value):
                found.append(SecretFinding(node_id, key, label))
                break
        else:
            if _SECRET_KEYS.search(key) and len(value) >= 8 and not value.startswith(("http", "/")):
                found.append(SecretFinding(node_id, key, f"field named {key!r}"))
    return found


def redact_workflow(workflow: Mapping[str, Any], findings: Sequence[SecretFinding],
                    replacement: str = REDACTED) -> Dict[str, Any]:
    """Copy with flagged widget values replaced: ``REDACTED`` for logs, ``""`` to strip before upload."""
    out = copy.deepcopy(dict(workflow))
    hits = {(f.node_id, f.field) for f in findings}
    if isinstance(out.get("nodes"), list):
        for node in out["nodes"]:
            vals = node.get("widgets_values") or []
            for i in range(len(vals)):
                if (str(node.get("id")), f"widgets_values[{i}]") in hits:
                    vals[i] = replacement
        return out
    for node_id, node in out.items():
        if isinstance(node, dict):
            for key in list((node.get("inputs") or {})):
                if (str(node_id), key) in hits:
                    node["inputs"][key] = replacement
    return out


class WeightClass(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class WeightVerdict:
    sha256: str
    name: str
    cls: WeightClass
    known: bool


def classify_weights(weights: Mapping[str, str], classes: Mapping[str, WeightClass]) -> List[WeightVerdict]:
    """``weights`` = sha256 -> display name. Unknown hashes warn and need acknowledgement."""
    out = []
    for sha, name in weights.items():
        cls = classes.get(sha)
        out.append(WeightVerdict(sha, name, cls or WeightClass.WARN, cls is not None))
    return out
