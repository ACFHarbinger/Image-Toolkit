"""
Tests for §1.8A — load_asp_config (backend/src/anim/config.py).
Tests for §1.8B — validate_asp_config schema validation.

Verifies TOML loading, env-var injection, setdefault precedence, multi-section
flattening, the override_env=False dry-run mode, and config schema validation.
"""

import os
import warnings

import pytest

from backend.src.anim.config import load_asp_config, validate_asp_config


class TestLoadAspConfig:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        result = load_asp_config(str(tmp_path / "nonexistent.toml"))
        assert result == {}

    def test_valid_config_sets_env_var(self, tmp_path, monkeypatch):
        cfg = tmp_path / "asp_config.toml"
        cfg.write_text("[frame_selection]\nASP_NEAR_DUP_LUMA = 7.5\n")
        monkeypatch.delenv("ASP_NEAR_DUP_LUMA", raising=False)
        result = load_asp_config(str(cfg))
        assert result.get("ASP_NEAR_DUP_LUMA") == pytest.approx(7.5)
        assert os.environ.get("ASP_NEAR_DUP_LUMA") == "7.5"

    def test_existing_env_var_not_overwritten(self, tmp_path, monkeypatch):
        cfg = tmp_path / "asp_config.toml"
        cfg.write_text("[frame_selection]\nASP_NEAR_DUP_LUMA = 7.5\n")
        monkeypatch.setenv("ASP_NEAR_DUP_LUMA", "3.0")
        load_asp_config(str(cfg))
        assert os.environ.get("ASP_NEAR_DUP_LUMA") == "3.0"

    def test_multi_section_keys_flattened(self, tmp_path, monkeypatch):
        cfg = tmp_path / "asp_config.toml"
        cfg.write_text(
            "[frame_selection]\nASP_HOLD_THRESHOLD = 0.03\n\n"
            "[compositing]\nASP_SP_SOFT_PX = 8\n"
        )
        monkeypatch.delenv("ASP_HOLD_THRESHOLD", raising=False)
        monkeypatch.delenv("ASP_SP_SOFT_PX", raising=False)
        result = load_asp_config(str(cfg))
        assert "ASP_HOLD_THRESHOLD" in result
        assert "ASP_SP_SOFT_PX" in result
        assert result["ASP_HOLD_THRESHOLD"] == pytest.approx(0.03)
        assert result["ASP_SP_SOFT_PX"] == 8

    def test_override_env_false_does_not_write_env(self, tmp_path, monkeypatch):
        cfg = tmp_path / "asp_config.toml"
        cfg.write_text("[pipeline]\nASP_COV_MIN_MULTI_PCT = 0.45\n")
        monkeypatch.delenv("ASP_COV_MIN_MULTI_PCT", raising=False)
        result = load_asp_config(str(cfg), override_env=False)
        assert result.get("ASP_COV_MIN_MULTI_PCT") == pytest.approx(0.45)
        assert "ASP_COV_MIN_MULTI_PCT" not in os.environ


# ---------------------------------------------------------------------------
# TestValidateAspConfig — §1.8B schema validation (S42)
# ---------------------------------------------------------------------------


class TestValidateAspConfig:
    """
    validate_asp_config(config, strict=False) checks known ASP keys against
    _CONFIG_SCHEMA: type correctness and min/max bounds.  Unknown keys emit a
    UserWarning but are not violations.  strict=True raises ValueError.
    """

    def test_valid_known_keys_return_empty_violations(self):
        """A well-formed config with schema-valid values must produce no violations."""
        config = {
            "ASP_HOLD_THRESHOLD": 0.03,
            "ASP_COV_MIN_MULTI_PCT": 0.30,
            "ASP_SP_SOFT_PX": 6,
            "ASP_POISSON_SEAM": 0,
        }
        assert validate_asp_config(config) == []

    def test_wrong_type_produces_violation(self):
        """A string value where float is expected must produce a violation message."""
        config = {"ASP_HOLD_THRESHOLD": "not-a-number"}
        violations = validate_asp_config(config)
        assert len(violations) == 1
        assert "ASP_HOLD_THRESHOLD" in violations[0]
        assert "float" in violations[0]

    def test_out_of_range_value_produces_violation(self):
        """A value exceeding the schema maximum must produce a violation message."""
        config = {"ASP_HIGH_HOLD_RESPONSE": 1.5}  # max is 1.0
        violations = validate_asp_config(config)
        assert len(violations) == 1
        assert "ASP_HIGH_HOLD_RESPONSE" in violations[0]
        assert "1.0" in violations[0]

    def test_strict_raises_on_violations(self):
        """strict=True must raise ValueError listing all violations."""
        config = {
            "ASP_HOLD_THRESHOLD": -0.1,   # below minimum 0.0
            "ASP_POISSON_SEAM": 2,         # exceeds maximum 1
        }
        with pytest.raises(ValueError, match="ASP config validation failed"):
            validate_asp_config(config, strict=True)

    def test_unknown_key_warns_but_not_a_violation(self):
        """An unrecognised key must emit UserWarning but not add a violation."""
        config = {"ASP_FUTURE_FLAG": 42}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            violations = validate_asp_config(config)
        assert violations == []
        assert any("ASP_FUTURE_FLAG" in str(w.message) for w in caught)
