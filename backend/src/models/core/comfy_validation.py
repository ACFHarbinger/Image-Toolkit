"""Pre-flight workflow validation (#738): check a curated template's node
types/inputs against a ComfyUI server's GET /object_info and the model
files it references against the model folders beneath ComfyUI's models
dir, before the workflow is uploaded.

Pure functions only — ComfyUIManager owns the fetch and cache; tests
exercise this module against a recorded /object_info fixture pinned to
the vendored vendor/ComfyUI submodule revision.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MISSING_NODE = "missing_node"
MISSING_INPUT = "missing_input"
UNKNOWN_INPUT = "unknown_input"
MISSING_FILE = "missing_file"

# Widget input name -> model subfolder(s) beneath ComfyUI's models dir,
# mirroring folder_names_and_paths in the vendored fork plus the folders
# custom-node packs register ("ipadapter"). /object_info choice lists are
# authoritative when a recording provides them; this map is the fallback
# for the local-disk existence half of the check.
MODEL_FILE_FOLDERS: dict[str, tuple[str, ...]] = {
    "ckpt_name": ("checkpoints",),
    "control_net_name": ("controlnet",),
    "ipadapter_file": ("ipadapter",),
    "vae_name": ("vae",),
    "lora_name": ("loras",),
    "clip_name": ("clip_vision", "text_encoders", "clip"),
    "unet_name": ("diffusion_models", "unet"),
    "diffusion_model_name": ("diffusion_models", "unet"),
    "upscale_model_name": ("upscale_models",),
    "style_model_name": ("style_models",),
}


@dataclass(frozen=True)
class TemplateIssue:
    """One reason a workflow graph cannot be queued as-is."""

    node_id: str | None
    input_name: str | None
    code: str  # one of the MISSING_*/UNKNOWN_* constants
    message: str


def _choice_list(spec: Any) -> list[str] | None:
    """Return the enumerated string choices of a widget spec, if any.

    /object_info serializes widget specs as ["TYPE", {opts}] or
    [[choice, ...], {opts}]; pins/links are plain "TYPE" strings.
    """
    if not (isinstance(spec, (list, tuple)) and spec):
        return None
    first = spec[0]
    if isinstance(first, (list, tuple)) and all(isinstance(v, str) for v in first):
        return list(first)
    return None


def _list_model_files(models_root: Path, folders: tuple[str, ...]) -> set[str]:
    """Recursive relative-path listing of *folders*, mirroring ComfyUI's
    folder_paths.get_filename_list (posix separators, nested subdirs)."""
    found: set[str] = set()
    for folder in folders:
        root = models_root / folder
        if not root.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                full = Path(dirpath) / filename
                found.add(full.relative_to(root).as_posix())
    return found


def _check_declared_inputs(
    node_ref: str,
    class_type: Any,
    inputs: dict[str, Any],
    spec: dict[str, Any],
) -> list[TemplateIssue]:
    """Input-name checks for one node against its /object_info class spec."""
    required = spec.get("required") or {}
    declared = (set(required) | set(spec.get("optional") or {})
                | set(spec.get("hidden") or {}))
    issues = []
    for name in inputs:
        if name not in declared:
            issues.append(TemplateIssue(node_ref, str(name), UNKNOWN_INPUT,
                                        f"node '{node_ref}' ({class_type}) has unknown input '{name}'"))
    for name in required:
        if name not in inputs:
            issues.append(TemplateIssue(node_ref, str(name), MISSING_INPUT,
                                        f"node '{node_ref}' ({class_type}) is missing input '{name}'"))
    return issues


def _check_file_input(
    node_ref: str,
    class_type: Any,
    name: str,
    value: Any,
    spec: dict[str, Any] | None,
    models_root: Path | None,
    local_files: dict[tuple[str, ...], set[str]],
) -> TemplateIssue | None:
    """Resolve one string-valued input against the server's choice list, or
    the local model folders when the spec declares no choice list."""
    if not isinstance(value, str) or not value:
        return None
    folders = MODEL_FILE_FOLDERS.get(name)
    if folders is None:
        return None
    choices = None
    if spec is not None:
        declared_spec = ((spec.get("required") or {}).get(name)
                         or (spec.get("optional") or {}).get(name))
        choices = _choice_list(declared_spec)
    if choices is not None:
        if value not in choices:
            return TemplateIssue(node_ref, str(name), MISSING_FILE,
                                 f"missing file '{value}' (input '{name}' of node "
                                 f"'{node_ref}') — not on the server's file list")
        return None
    if models_root is None:
        return None
    if folders not in local_files:
        local_files[folders] = _list_model_files(models_root, folders)
    if value not in local_files[folders]:
        return TemplateIssue(node_ref, str(name), MISSING_FILE,
                             f"missing file '{value}' (input '{name}' of node "
                             f"'{node_ref}') — not under {models_root / folders[0]}")
    return None


def validate_template(
    template: dict[str, Any],
    object_info: dict[str, Any] | None = None,
    *,
    models_root: Path | None = None,
) -> list[TemplateIssue]:
    """Validate an API-format prompt graph (node id -> {inputs, class_type}).

    With *object_info*, each node's class type must exist and its inputs
    must cover the class's required inputs and stay within its declared
    required/optional/hidden sets. Model-file inputs in MODEL_FILE_FOLDERS
    must resolve against the server's choice list when one is declared,
    otherwise against *models_root* on local disk. Without *object_info*
    only the local file checks run.
    """
    issues: list[TemplateIssue] = []
    local_files: dict[tuple[str, ...], set[str]] = {}
    for node_id, node in template.items():
        node_ref = str(node_id)
        if not isinstance(node, dict):
            issues.append(TemplateIssue(node_ref, None, MISSING_NODE,
                                        f"node '{node_ref}' is not an object"))
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs") or {}
        spec: dict[str, Any] | None = None
        if object_info is not None:
            info = object_info.get(class_type) if isinstance(class_type, str) else None
            if info is None:
                issues.append(TemplateIssue(node_ref, None, MISSING_NODE,
                                            f"missing node '{class_type}' (used by node '{node_ref}')"))
                continue
            spec = info.get("input") or {}
            issues.extend(_check_declared_inputs(node_ref, class_type, inputs, spec))
        for name, value in inputs.items():
            issue = _check_file_input(node_ref, class_type, name, value,
                                      spec, models_root, local_files)
            if issue is not None:
                issues.append(issue)
    return issues
