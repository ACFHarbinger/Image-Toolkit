"""MkDocs hooks — symlink moon/ and research/ content into docs/ at build time.

Called by the `hooks:` key in mkdocs.yml. Creates the docs/roadmaps/,
docs/research/, and stub API pages that the nav references.
"""

from __future__ import annotations

import os
import re
import shutil
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"

SOURCE_TO_DEST: dict[Path, Path] = {}
DEST_TO_SOURCE: dict[Path, Path] = {}


def on_pre_build(config: dict) -> None:
    """Copy roadmap and report sources into the docs tree before building."""
    # Clean up old README.md files to prevent index.md conflicts
    readme_path = DOCS / "README.md"
    if readme_path.exists():
        readme_path.unlink()
    ts_readme_path = DOCS / "api" / "typescript" / "README.md"
    if ts_readme_path.exists():
        ts_readme_path.unlink()

    # Pre-populate exact redirects for merged reports
    merged_reports = [
        "ASP Consolidated Research Plan.md",
        "Anime Stitch Pipeline ML Research.md",
        "Multi-modal Anime Panorama Stitching.md",
        "Multimodal_ASP_HITL_Research.md",
        "Upgrading Anime Stitch Pipeline.md",
        "ASP_Consolidated_Research_Plan.md",
        "Anime_Stitch_Pipeline_ML_Research.md",
        "Multi-modal_Anime_Panorama_Stitching.md",
    ]
    for r in merged_reports:
        SOURCE_TO_DEST[ROOT / "research" / r] = DOCS / "research" / "asp_research.md"

    # Pre-populate exact redirects for READMEs
    SOURCE_TO_DEST[ROOT / "README.md"] = DOCS / "readme.md"
    SOURCE_TO_DEST[DOCS / "README.md"] = DOCS / "readme.md"
    SOURCE_TO_DEST[ROOT / "frontend" / "README.md"] = DOCS / "api" / "typescript" / "readme.md"
    SOURCE_TO_DEST[DOCS / "api" / "typescript" / "README.md"] = DOCS / "api" / "typescript" / "readme.md"

    _sync_dir(ROOT / "moon" / "roadmaps", DOCS / "roadmaps")
    _sync_dir(ROOT / "moon", DOCS, only=["CHANGELOG.md"])
    _sync_dir(ROOT / "moon", DOCS / "roadmaps", only=["ROADMAP.md"])
    _sync_dir(ROOT, DOCS, only=["README.md"], rename={"README.md": "readme.md"})
    _sync_dir(ROOT / "frontend", DOCS / "api" / "typescript", only=["README.md"], rename={"README.md": "readme.md"})
    _sync_dir(
        ROOT / "research",
        DOCS / "research",
        rename={
            "Analytics and Codebase Visualization Research.md": "analytics.md",
            "ASP_Comprehensive_Research_Report.md": "asp_research.md",
            "Image_Generation_Research.md": "image_generation.md",
            "Image_Stitching_Research.md": "image_stitching.md",
        },
    )
    _sync_dir(
        ROOT / "docs",
        DOCS,
        only=[
            "ARCHITECTURE.md",
            "BENCHMARKS.md",
            "DEPENDENCY_POLICY.md",
            "DOCUMENTATION_STANDARDS.md",
            "TROUBLESHOOTING.md",
            "STRUCTURIZR.md",
        ],
    )

    # Populate self-mappings for other files under docs/
    for doc_file in DOCS.rglob("*.md"):
        resolved = doc_file.resolve()
        if resolved not in DEST_TO_SOURCE:
            DEST_TO_SOURCE[resolved] = resolved
            SOURCE_TO_DEST[resolved] = resolved

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

        src_file_resolved = src_file.resolve()
        dst_file_resolved = dst_file.resolve()
        SOURCE_TO_DEST[src_file_resolved] = dst_file_resolved
        DEST_TO_SOURCE[dst_file_resolved] = src_file_resolved

        if src_file_resolved == dst_file_resolved:
            continue
        shutil.copy2(src_file, dst_file)


def on_page_markdown(markdown: str, page, config, files) -> str:
    """Rewrite relative markdown links to match the new docs structure."""
    # Fix TypeDoc rendering of array types like `type`[][] or `type`[] causing empty reference link warnings
    markdown = re.sub(r'`([^`]+)`\[\]\[\]', r'`\1[][]`', markdown)
    markdown = re.sub(r'`([^`]+)`\[\]', r'`\1[]`', markdown)

    abs_src_path = Path(page.file.abs_src_path).resolve()
    orig_src_path = DEST_TO_SOURCE.get(abs_src_path, abs_src_path)
    orig_src_dir = orig_src_path.parent

    # Regex to match markdown links: [text](url)
    pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    def replace_link(match: re.Match) -> str:
        text = match.group(1)
        url_part = match.group(2).strip()

        # Handle title in link
        parts = url_part.split(None, 1)
        url = parts[0]
        title = f" {parts[1]}" if len(parts) > 1 else ""

        if (
            url.startswith(("http://", "https://", "mailto:", "ftp:", "git:", "ssh:"))
            or url.startswith("#")
        ):
            return match.group(0)

        unquoted_url = urllib.parse.unquote(url)
        url_parsed = urllib.parse.urlparse(unquoted_url)
        path_part = url_parsed.path
        fragment = url_parsed.fragment
        query = url_parsed.query

        if not path_part:
            return match.group(0)

        target_src_abs = (orig_src_dir / path_part).resolve()

        if target_src_abs in SOURCE_TO_DEST:
            target_dst_abs = SOURCE_TO_DEST[target_src_abs]
            dst_dir = abs_src_path.parent
            try:
                new_rel_path = os.path.relpath(target_dst_abs, dst_dir)
            except ValueError:
                new_rel_path = str(target_dst_abs)

            quoted_rel_path = urllib.parse.quote(new_rel_path)
            new_url = quoted_rel_path
            if query:
                new_url += f"?{query}"
            if fragment:
                new_url += f"#{fragment}"

            return f"[{text}]({new_url}{title})"

        # Check if it's a file under the project root
        is_rel = False
        try:
            target_src_abs.relative_to(ROOT)
            is_rel = True
        except ValueError:
            pass

        if is_rel:
            try:
                rel_to_root = target_src_abs.relative_to(ROOT)
                is_directory = (ROOT / rel_to_root).is_dir() if (ROOT / rel_to_root).exists() else False
                subpath_type = "tree" if is_directory else "blob"
                github_url = f"https://github.com/ACFPeacekeeper/Image-Toolkit/{subpath_type}/main/{rel_to_root.as_posix()}"
                if query:
                    github_url += f"?{query}"
                if fragment:
                    github_url += f"#{fragment}"
                return f"[{text}]({github_url}{title})"
            except Exception:
                pass

        return match.group(0)

    return pattern.sub(replace_link, markdown)


def _ensure_stub_api_pages() -> None:
    """Create minimal stub pages for API sections that use mkdocstrings."""
    stubs = {
        DOCS / "api" / "python" / "animation.md": (
            "# ASP / Animation Module API\n\n"
            "::: backend.src.animation.core.pipeline\n\n"
            "::: backend.src.animation.rendering.compositing\n\n"
            "::: backend.src.animation.ingestion.frame_selection\n\n"
            "::: backend.src.animation.alignment.bundle_adjust\n"
        ),
        DOCS / "api" / "python" / "core.md": (
            "# Backend Core API\n\n"
            "::: backend.src.database.image_database\n\n"
            "::: backend.src.core.vault_manager\n"
        ),
        DOCS / "api" / "python" / "models.md": (
            "# ML Models API\n\n::: backend.src.models.core.base\n"
        ),
        DOCS / "api" / "rust" / "math.md": (
            "# C++ Math Backbone\n\n"
            "The C++ math backbone is documented via `cargo doc`.\n\n"
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
| `mkdocstrings` (this portal) | Key `animation/`, `core/`, `models/` modules | Rendered inline | Quick lookup while reading roadmaps |
| Sphinx + autoapi (separate artifact) | All of `backend/src/` | Standalone HTML site | Deep-dive reference, cross-links to NumPy/PyTorch |

!!! info "Configuration"
    Sphinx configuration lives in `docs/sphinx/conf.py`. The build uses:

    - **Theme**: [Furo](https://pradyunsg.me/furo/)
    - **Auto-discovery**: `sphinx-autoapi` (no manual module listing needed)
    - **Docstring style**: Google (via `sphinx.ext.napoleon`)
    - **Notebook pages**: `myst-nb` with `nb_execution_mode = "off"`
"""
