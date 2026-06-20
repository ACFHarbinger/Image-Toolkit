"""MkDocs hooks — symlink moon/ and reports/ content into docs/ at build time.

Called by the `hooks:` key in mkdocs.yml. Creates the docs/roadmaps/,
docs/reports/, and stub API pages that the nav references.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"


def on_pre_build(config: dict) -> None:
    """Copy roadmap and report sources into the docs tree before building."""
    _sync_dir(ROOT / "moon" / "roadmaps", DOCS / "roadmaps")
    _sync_dir(ROOT / "moon", DOCS, only=["CHANGELOG.md", "ROADMAP.md"])
    _sync_dir(ROOT / "reports", DOCS / "reports", rename={
        "Analytics and Codebase Visualization Research.md": "analytics.md",
        "ASP_Comprehensive_Research_Report.md": "asp_research.md",
        "Image_Generation_Research.md": "image_generation.md",
        "Image_Stitching_Research.md": "image_stitching.md",
    })
    _sync_dir(ROOT / "docs", DOCS, only=[
        "ARCHITECTURE.md", "BENCHMARKS.md", "DEPENDENCY_POLICY.md",
        "DOCUMENTATION_STANDARDS.md", "TROUBLESHOOTING.md", "STRUCTURIZR.md",
    ])
    _ensure_stub_api_pages()


def _sync_dir(
    src: Path,
    dst: Path,
    *,
    only: list[str] | None = None,
    rename: dict[str, str] | None = None,
) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for src_file in src.glob("*.md"):
        target_name = (rename or {}).get(src_file.name, src_file.name)
        if only and src_file.name not in only:
            continue
        dst_file = dst / target_name
        shutil.copy2(src_file, dst_file)


def _ensure_stub_api_pages() -> None:
    """Create minimal stub pages for API sections that use mkdocstrings."""
    stubs = {
        DOCS / "api" / "python" / "anim.md": (
            "# ASP / Animation Module API\n\n"
            "::: backend.src.anim.pipeline\n\n"
            "::: backend.src.anim.compositing\n\n"
            "::: backend.src.anim.frame_selection\n\n"
            "::: backend.src.anim.bundle_adjust\n"
        ),
        DOCS / "api" / "python" / "core.md": (
            "# Backend Core API\n\n"
            "::: backend.src.core.image_database\n\n"
            "::: backend.src.core.vault_manager\n"
        ),
        DOCS / "api" / "python" / "models.md": (
            "# ML Models API\n\n"
            "::: backend.src.models.base\n"
        ),
        DOCS / "api" / "rust" / "math.md": (
            "# Rust Math Backbone\n\n"
            "The Rust math backbone is documented via `cargo doc`.\n\n"
            "Run `cd base && cargo doc --no-deps --open` to browse the "
            "rendered HTML reference locally.\n\n"
            "Key modules: `base::math::linalg`, `base::math::stats`, "
            "`base::math::distance`, `base::math::information`, "
            "`base::math::graph`, `base::math::dim_reduce`.\n"
        ),
        DOCS / "api" / "kotlin" / "index.md": _kotlin_stub(),
        DOCS / "api" / "sphinx.md": _sphinx_stub(),
        DOCS / "api" / "rest-api.md": _rest_api_stub(),
    }
    for path, content in stubs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content)


def _kotlin_stub() -> str:
    return """\
# Android Kotlin API (Dokka GFM)

The Android module (`app/android/`) is documented via
[Dokka](https://kotlinlang.org/docs/dokka-introduction.html) in
GitHub-Flavoured Markdown format.

## Generating the docs locally

```bash
cd app/android
./gradlew dokkaGfm
# Output → app/android/build/dokka/gfm/
open app/android/build/dokka/gfm/index.md
```

## CI artifact

In GitHub Actions, the `docs-kotlin` job runs `./gradlew dokkaGfm` and
uploads the output as the **`kotlin-api-docs`** artifact (7-day retention).
Download it from the Actions run to browse the full reference.

## Module overview

| Package | Purpose |
|---------|---------|
| `com.personal.image_toolkit` | Application entry point (`AppActivity`) |
| `com.personal.image_toolkit.classes` | Abstract base fragments (`BaseSingleGalleryFragment`, `BaseTwoGalleriesFragment`, `BaseGenerativeFragment`) |
| `com.personal.image_toolkit.ui` | Feature screens — slideshow, settings, convert, wallpaper |
| `com.personal.image_toolkit.ui.windows` | Full-screen windows — login, image preview, log |

!!! note "Dokka configuration"
    The Dokka Gradle plugin (`org.jetbrains.dokka`) is declared in
    `app/android/build.gradle.kts`. Run `./gradlew dokkaHtml` for the richer
    interactive HTML reference; `./gradlew dokkaGfm` for the Markdown version
    that integrates with this portal.
"""


def _rest_api_stub() -> str:
    return """\
# REST API Reference

This page is auto-generated. The full REST API documentation is available at
`docs/api/rest-api.md`. If you are reading this stub, the hooks.py sync has not
yet replaced it — run `mkdocs build` locally to regenerate.

See [REST API](rest-api.md) for the full reference including all 21 endpoints,
interactive Swagger UI instructions, and the OpenAPI 3.1 spec generation guide.
"""


def _sphinx_stub() -> str:
    return """\
# Python Backend Reference (Sphinx)

The comprehensive Python backend reference is generated by
[Sphinx](https://www.sphinx-doc.org/) with
[sphinx-autoapi](https://sphinx-autoapi.readthedocs.io/), which auto-discovers
every module in `backend/src/` without requiring manual `.. automodule::`
directives.

## Generating the docs locally

```bash
pip install sphinx sphinx-autoapi furo myst-nb sphinx-copybutton
sphinx-build -b html docs/sphinx site/sphinx-api
open site/sphinx-api/index.html
```

Or use the provided requirements file:

```bash
pip install -r docs/sphinx/requirements.txt
sphinx-build -b html docs/sphinx site/sphinx-api
```

## CI artifact

The `docs-sphinx` GitHub Actions job builds the Sphinx HTML and stores it as
the **`sphinx-api-docs`** artifact (14-day retention).

## Relationship to mkdocstrings

| Tool | Scope | Format | When to use |
|------|-------|--------|-------------|
| `mkdocstrings` (this portal) | Key `anim/`, `core/`, `models/` modules | Rendered inline | Quick lookup while reading roadmaps |
| Sphinx + autoapi (separate artifact) | All of `backend/src/` | Standalone HTML site | Deep-dive reference, cross-links to NumPy/PyTorch |

!!! info "Configuration"
    Sphinx configuration lives in `docs/sphinx/conf.py`. The build uses:

    - **Theme**: [Furo](https://pradyunsg.me/furo/)
    - **Auto-discovery**: `sphinx-autoapi` (no manual module listing needed)
    - **Docstring style**: Google (via `sphinx.ext.napoleon`)
    - **Notebook pages**: `myst-nb` with `nb_execution_mode = "off"`
"""
