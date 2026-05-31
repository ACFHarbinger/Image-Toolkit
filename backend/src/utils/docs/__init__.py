"""
Documentation utilities module.

Attributes:
    check_docstrings: Check a single .py file and return a list of violation dicts.
    check_docstrings_recursive: Recursively collect violations from all .py files under *directory*.
    display_results: Render the violation report as a Rich table grouped by file.
    check_google_style: Check a single .py file and return a list of violation dicts.
    display_report: Displays the violations in a Rich table.
    main: Main entry point.
    add_docstrings_batch: Add docstrings to a Python file.
    DocstringInjector: Class for injecting docstrings into Python files.
    main: Main entry point.

Example:
    python -m src.utils.docs.check_docstrings <path1> [path2 ...]
    python -m src.utils.docs.check_google_style <path1> [path2 ...]
    python -m src.utils.docs.add_docstrings_batch <path1> [path2 ...]
"""
