"""Sphinx configuration for the Image Toolkit Python backend reference.

Run: sphinx-build -b html docs/sphinx site/sphinx-api
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── sys.path for autodoc imports ─────────────────────────────────────────────
# Allows autoapi to import backend.src.* without installing the package.
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT))

# ── Project metadata ─────────────────────────────────────────────────────────
project = "Image Toolkit — Python Backend"
author = "ACFPeacekeeper"
release = "0.1.0"
html_title = "Image Toolkit Python Reference"
copyright = "2026, ACFPeacekeeper"

# ── Extensions ───────────────────────────────────────────────────────────────
extensions = [
    "autoapi.extension",      # auto-discover all modules without rst stubs
    "sphinx.ext.napoleon",    # Google-style and NumPy-style docstrings
    "sphinx.ext.viewcode",    # [source] links on every API page
    "sphinx.ext.intersphinx", # cross-references to Python stdlib / NumPy / PyTorch
    "myst_nb",                # render .ipynb notebooks as Sphinx pages
    "sphinx_copybutton",      # one-click code-block copy
]

# ── sphinx-autoapi ────────────────────────────────────────────────────────────
autoapi_dirs = [str(REPO_ROOT / "backend" / "src")]
autoapi_type = "python"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_ignore = [
    "**/test_*.py",
    "**/__pycache__/**",
    "**/conftest.py",
]
# Emit a toctree entry from autoapi/index.rst so it appears in the main TOC.
autoapi_add_toctree_entry = True
autoapi_keep_files = False

# ── myst-nb (notebooks) ──────────────────────────────────────────────────────
# Notebooks are already stripped of outputs by nbstripout (pre-commit hook).
# "off" means cells are rendered as static code/markdown blocks — no execution.
nb_execution_mode = "off"
nb_execution_timeout = 0
myst_enable_extensions = ["colon_fence", "deflist", "dollarmath"]

# ── Napoleon ─────────────────────────────────────────────────────────────────
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_returns = True
napoleon_preprocess_types = True

# ── Intersphinx ──────────────────────────────────────────────────────────────
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "torch": ("https://pytorch.org/docs/stable/", None),
    "cv2": ("https://docs.opencv.org/4.x/", None),
}

# ── HTML (Furo theme) ────────────────────────────────────────────────────────
html_theme = "furo"
html_static_path = ["_static"]
templates_path = ["_templates"]
html_theme_options = {
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#3949ab",
        "color-brand-content": "#3949ab",
    },
    "dark_css_variables": {
        "color-brand-primary": "#7986cb",
        "color-brand-content": "#7986cb",
    },
}

# ── Build behaviour ───────────────────────────────────────────────────────────
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]
# nitpicky = True would fail on every unresolved cross-reference — leave off
# until intersphinx covers all deps.
nitpicky = False
