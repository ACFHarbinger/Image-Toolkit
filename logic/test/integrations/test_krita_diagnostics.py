"""Tests for Krita compatibility diagnostics without importing Krita."""

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[3] / "integrations/krita/pykrita/cel_shaded_generator/diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("krita_plugin_diagnostics", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
diagnostics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostics
SPEC.loader.exec_module(diagnostics)
diagnose = diagnostics.diagnose


def test_supported_version_and_packaged_content_are_compatible(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "lesson.json").write_text("{}", encoding="utf-8")

    report = diagnose("5.2.11-prealpha", tmp_path)

    assert report.compatible
    assert report.content_available
    assert report.python_version


def test_old_or_unparseable_krita_is_rejected(tmp_path):
    for version in ("5.1.9", "unknown"):
        report = diagnose(version, tmp_path)
        assert not report.compatible
        assert any("Krita 5.2" in message for message in report.messages)


def test_missing_content_is_actionable(tmp_path):
    report = diagnose("5.2.11", tmp_path)
    assert not report.compatible
    assert "Packaged lesson content is missing." in report.messages
