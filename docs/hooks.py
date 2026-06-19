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
        "DOCUMENTATION_STANDARDS.md", "TROUBLESHOOTING.md",
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
    }
    for path, content in stubs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content)
