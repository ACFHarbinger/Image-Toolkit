"""Unit tests for backend/src/utils/data/safetensors_metadata.py."""

import os
import tempfile

from backend.src.utils.data.safetensors_metadata import (
    calculate_file_hash,
    parse_model_spec,
    read_metadata,
)


def test_parse_model_spec_lora():
    meta = {
        "ss_network_dim": "32",
        "ss_network_alpha": "16",
        "ss_sd_model_name": "SD 1.5 Base",
        "modelspec.trigger_phrase": "anime girl, masterpiece",
        "ss_sha256": "abc123def456",
    }
    parsed = parse_model_spec(meta)
    assert parsed["rank"] == "32"
    assert parsed["alpha"] == "16"
    assert parsed["base_model"] == "SD 1.5 Base"
    assert parsed["trigger_words"] == "anime girl, masterpiece"
    assert parsed["embedded_hash"] == "abc123def456"


def test_calculate_file_hash():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"safetensors test binary header data")
        temp_path = f.name

    try:
        hash_val = calculate_file_hash(temp_path)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 hex digest length
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_read_metadata_nonexistent():
    res = read_metadata("/nonexistent/file/path.safetensors")
    assert res["tensor_count"] == 0
    assert res["user_meta"] == {}
