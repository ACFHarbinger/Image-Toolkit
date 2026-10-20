"""Runtime JSON-Schema validation for bridge envelopes (W0-11, #875).

The contract types in ``contracts/generated/`` are typing-only; this module
is the runtime enforcement point. It implements exactly the JSON-Schema
(draft 2020-12) subset the contract files use today and fails loudly on an
unknown keyword, so a schema that grows beyond the subset breaks at load
time instead of validating loosely.

Supported keywords: ``type`` (string or list), ``const``, ``enum``,
``pattern``, ``required``, ``properties``, ``additionalProperties: false``,
``minLength``, ``minimum``, ``maximum``, ``items``, ``uniqueItems``,
``$defs``, ``$ref`` (same-document ``#/$defs/...`` and cross-file),
``oneOf`` (``$ref`` branches only). ``format`` is annotation-only, as in
the draft. Everything else raises ``UnsupportedSchema``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Root-level annotation keywords; ignored, never asserted.
_ANNOTATIONS = frozenset({"$schema", "$id", "title", "description", "format"})
# Keywords a schema object may carry. Unknown ones fail loud.
_KEYWORDS = (
    frozenset(
        {
            "type",
            "const",
            "enum",
            "pattern",
            "required",
            "properties",
            "additionalProperties",
            "minLength",
            "minimum",
            "maximum",
            "items",
            "uniqueItems",
            "$defs",
            "$ref",
            "oneOf",
        }
    )
    | _ANNOTATIONS
)

_TYPE_CHECKS: dict[str, Any] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class UnsupportedSchema(Exception):
    """A contract schema uses a keyword this validator does not implement."""


@dataclass(frozen=True)
class SchemaError:
    """One validation failure, at a dotted path inside the instance."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _json_key(value: Any) -> str:
    # bool is an int subclass in Python but a distinct JSON type; keep the
    # keys apart so const/enum/uniqueItems never conflate 1 with True.
    if isinstance(value, bool):
        return f"b:{value}"
    if isinstance(value, (dict, list)):
        import json

        return f"j:{json.dumps(value, sort_keys=True, separators=(',', ':'))}"
    return f"{type(value).__name__}:{value!r}"


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


class SchemaRegistry:
    """Loads the contract schema tree and resolves ``$ref`` across files."""

    def __init__(self, schemas_dir: Path) -> None:
        self._schemas_dir = schemas_dir
        # Keyed by the path relative to the schemas root ("envelope/request.json").
        self._docs: dict[str, dict[str, Any]] = {}

    def document(self, rel_path: str) -> dict[str, Any]:
        doc = self._docs.get(rel_path)
        if doc is None:
            path = self._schemas_dir / rel_path
            import json

            doc = json.loads(path.read_text(encoding="utf-8"))
            self._check_keywords(doc, rel_path)
            self._docs[rel_path] = doc
        return doc

    def _check_keywords(self, schema: dict[str, Any], where: str) -> None:
        if not isinstance(schema, dict):
            return
        unknown = set(schema) - _KEYWORDS
        if unknown:
            raise UnsupportedSchema(
                f"unsupported JSON-Schema keyword(s) {sorted(unknown)} in {where}; "
                "extend middleware/src/bridge/schema.py to match the contract"
            )
        for sub in schema.get("$defs", {}).values():
            self._check_keywords(sub, where)
        for sub in schema.get("properties", {}).values():
            self._check_keywords(sub, where)
        if isinstance(schema.get("items"), dict):
            self._check_keywords(schema["items"], where)
        for sub in schema.get("oneOf", []):
            if "$ref" not in sub:
                raise UnsupportedSchema(f"oneOf branch without $ref in {where}")

    def _resolve(self, ref: str, base_path: str) -> tuple[dict[str, Any], str]:
        import posixpath

        if ref.startswith("#"):
            return self.document(base_path), ref
        file_part, _, fragment = ref.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), file_part))
        return self.document(target), fragment or "#"

    def validate(self, instance: Any, schema_ref: str, base_path: str) -> list[SchemaError]:
        """Validate ``instance`` against a schema (``schema_ref`` is a ``$ref``)."""
        doc, fragment = self._resolve(schema_ref, base_path)
        if fragment.startswith("#/$defs/"):
            name = fragment.removeprefix("#/$defs/")
            schema = doc.get("$defs", {}).get(name)
            if schema is None:
                raise UnsupportedSchema(f"unknown $defs entry {fragment} in {base_path}")
        elif fragment == "#":
            schema = doc
        else:
            raise UnsupportedSchema(f"unsupported $ref fragment {fragment!r} in {base_path}")
        errors: list[SchemaError] = []
        self._check(instance, schema, "", base_path, errors)
        return errors

    # ``path`` is the dotted location inside the instance ("" at the root).
    def _check(
        self,
        instance: Any,
        schema: dict[str, Any],
        path: str,
        base_path: str,
        errors: list[SchemaError],
    ) -> None:
        if "$ref" in schema:
            doc, fragment = self._resolve(schema["$ref"], base_path)
            target = doc if fragment == "#" else doc["$defs"][fragment.removeprefix("#/$defs/")]
            self._check(instance, target, path, base_path, errors)
            return

        if "oneOf" in schema:
            for branch in schema["oneOf"]:
                branch_errors: list[SchemaError] = []
                self._check(instance, branch, path, base_path, branch_errors)
                if not branch_errors:
                    return
            errors.append(SchemaError(path or "$", "matches none of the oneOf branches"))
            return

        expected = schema.get("type")
        if expected is not None:
            names = expected if isinstance(expected, list) else [expected]
            for name in names:
                if name not in _TYPE_CHECKS:
                    raise UnsupportedSchema(f"unknown JSON type {name!r}")
            if not any(_TYPE_CHECKS[name](instance) for name in names):
                errors.append(SchemaError(path or "$", f"expected {expected}, got {_type_name(instance)}"))
                return

        self._check_scalar(instance, schema, path, errors)

        if isinstance(instance, dict):
            self._check_object(instance, schema, path, base_path, errors)
        elif isinstance(instance, list):
            self._check_array(instance, schema, path, base_path, errors)

    def _check_scalar(
        self,
        instance: Any,
        schema: dict[str, Any],
        path: str,
        errors: list[SchemaError],
    ) -> None:
        if "const" in schema and _json_key(instance) != _json_key(schema["const"]):
            errors.append(SchemaError(path or "$", f"must be {schema['const']!r}"))
        if "enum" in schema:
            keys = {_json_key(v) for v in schema["enum"]}
            if _json_key(instance) not in keys:
                errors.append(SchemaError(path or "$", f"must be one of {schema['enum']!r}"))
        if isinstance(instance, str):
            pattern = schema.get("pattern")
            if pattern is not None and re.search(pattern, instance) is None:
                errors.append(SchemaError(path or "$", f"does not match pattern {pattern!r}"))
            min_length = schema.get("minLength")
            if min_length is not None and len(instance) < min_length:
                errors.append(SchemaError(path or "$", f"shorter than minLength {min_length}"))
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            minimum = schema.get("minimum")
            if minimum is not None and instance < minimum:
                errors.append(SchemaError(path or "$", f"below minimum {minimum}"))
            maximum = schema.get("maximum")
            if maximum is not None and instance > maximum:
                errors.append(SchemaError(path or "$", f"above maximum {maximum}"))

    def _check_object(
        self,
        instance: dict[str, Any],
        schema: dict[str, Any],
        path: str,
        base_path: str,
        errors: list[SchemaError],
    ) -> None:
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(SchemaError(f"{path}.{name}" if path else name, "is required"))
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties")
        for key, value in instance.items():
            child = f"{path}.{key}" if path else key
            if key in props:
                self._check(value, props[key], child, base_path, errors)
            elif additional is False:
                errors.append(SchemaError(child, "additional property not allowed"))

    def _check_array(
        self,
        instance: list[Any],
        schema: dict[str, Any],
        path: str,
        base_path: str,
        errors: list[SchemaError],
    ) -> None:
        items = schema.get("items")
        for index, item in enumerate(instance):
            child = f"{path}[{index}]"
            if isinstance(items, dict):
                self._check(item, items, child, base_path, errors)
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for item in instance:
                key = _json_key(item)
                if key in seen:
                    errors.append(SchemaError(path or "$", "items are not unique"))
                    break
                seen.add(key)
