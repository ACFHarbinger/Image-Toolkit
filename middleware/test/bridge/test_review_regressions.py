"""Runtime-validation and error-redaction regressions from review."""

import io
import json

import pytest

from middleware.src.bridge.envelope import BridgeAppError, from_exception
from middleware.src.bridge.framing import iter_frames
from middleware.src.bridge.schema import SchemaRegistry


def test_error_mapping_does_not_echo_secret_values():
    error = from_exception(ValueError("invalid api_key=very-secret-token"))
    assert "very-secret-token" not in json.dumps(error.envelope())


def test_nonfinite_values_are_not_wire_json():
    with pytest.raises(BridgeAppError):
        list(iter_frames(io.StringIO('{"value":NaN}\n')))


def test_numeric_overflow_is_a_parse_error():
    with pytest.raises(BridgeAppError) as exc_info:
        list(iter_frames(io.StringIO('{"value":1e999}\n')))
    assert exc_info.value.code == "bridge.parse_error"


def test_nested_numeric_overflow_is_a_parse_error():
    with pytest.raises(BridgeAppError) as exc_info:
        list(iter_frames(io.StringIO('{"params":{"value":1e999}}\n')))
    assert exc_info.value.code == "bridge.parse_error"


def test_finite_floats_still_parse():
    frames = list(iter_frames(io.StringIO('{"value":1.5}\n')))
    assert frames == [{"value": 1.5}]


def test_cross_file_refs_keep_the_referenced_document_base(tmp_path):
    (tmp_path / "child.json").write_text(
        json.dumps(
            {
                "$defs": {"Id": {"type": "integer"}},
                "type": "object",
                "properties": {"id": {"$ref": "#/$defs/Id"}},
            }
        )
    )
    (tmp_path / "root.json").write_text(json.dumps({"$ref": "child.json"}))
    registry = SchemaRegistry(tmp_path)
    assert registry.validate({"id": 5}, "#", "root.json") == []
    assert registry.validate({"id": "bad"}, "#", "root.json")


def test_oneof_requires_exactly_one_match(tmp_path):
    (tmp_path / "root.json").write_text(
        json.dumps(
            {
                "$defs": {"A": {"type": "integer"}, "B": {"type": "number"}},
                "oneOf": [{"$ref": "#/$defs/A"}, {"$ref": "#/$defs/B"}],
            }
        )
    )
    assert SchemaRegistry(tmp_path).validate(1, "#", "root.json")
