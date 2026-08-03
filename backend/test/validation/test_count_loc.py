"""Unit tests for backend/validation/count_loc.py."""

import os
import tempfile

from backend.validation.count_loc import analyze_file, generate_markdown_report, load_exceptions


def test_analyze_file_counts():
    content = '''"""Module docstring.
Line 2 of docstring."""

# A comment line
x = 1
y = 2  # inline comment
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        metrics = analyze_file(temp_path)
        assert metrics["code"] == 2
        assert metrics["comment"] == 1
        assert metrics["docstring"] == 2
        assert metrics["total"] == 5
    finally:
        os.remove(temp_path)


def test_load_exceptions():
    content = """# Exceptions list
gui/src/helpers/animation/stitch_worker/_progress_pipeline.py

# another comment
some/path/file.py
"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        exceptions = load_exceptions(temp_path)
        assert len(exceptions) == 2
        assert os.path.normpath("gui/src/helpers/animation/stitch_worker/_progress_pipeline.py") in exceptions
        assert os.path.normpath("some/path/file.py") in exceptions
    finally:
        os.remove(temp_path)


def test_generate_markdown_report():
    display_data = [
        {"path": "foo.py", "code": 100, "comment": 10, "docstring": 20, "total": 130},
        {"path": "bar.py", "code": 50, "comment": 5, "docstring": 10, "total": 65},
    ]
    report = generate_markdown_report(display_data, display_data, limit=10, sort_key="code")
    assert "# Codebase Line-Count Analysis Report" in report
    assert "`foo.py` | 100" in report
    assert "`bar.py` | 50" in report
    assert "**TOTALS** | **150**" in report
