"""Unit tests for middleware/validation/check_docs_freshness.py (Issue #885, W0-21)."""

from __future__ import annotations

from pathlib import Path

from middleware.validation.check_docs_freshness import (
    parse_contracts_sha256,
    validate_docs_spine,
)


def test_live_repo_docs_spine_is_fresh():
    repo_root = Path(__file__).resolve().parents[3]
    errors = validate_docs_spine(repo_root)
    assert errors == []


def test_detects_stale_contract_hash_and_missing_sections(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    good_hash = "a" * 64
    stale_hash = "b" * 64
    (contracts_dir / "CONTRACTS.sha256").write_text(
        f"total  {good_hash}\n{good_hash}  contracts/schemas/capability/system.json\n",
        encoding="utf-8",
    )

    parsed = parse_contracts_sha256(contracts_dir / "CONTRACTS.sha256")
    assert parsed["total"] == good_hash
    assert parsed["contracts/schemas/capability/system.json"] == good_hash

    docs_dir = tmp_path / "docs"
    (docs_dir / "adr").mkdir(parents=True)
    (docs_dir / "modules").mkdir(parents=True)

    (docs_dir / "ARCHITECTURE.md").write_text(
        "# Architecture\n## C4 Level 1\n## C4 Level 2\n## C4 Level 3\n",
        encoding="utf-8",
    )
    (docs_dir / "ASP_ARCHITECTURE.md").write_text("# ASP\n", encoding="utf-8")
    (docs_dir / "adr" / "0001-sample.md").write_text("# ADR-0001\n", encoding="utf-8")
    (docs_dir / "adr" / "index.md").write_text(
        "# ADRs\n| [ADR-0001](0001-sample.md) |\n",
        encoding="utf-8",
    )

    template_body = (
        "# Template\n"
        "| Field | Value |\n|---|---|\n"
        "| **Contract Schema** | `contracts/CONTRACTS.sha256` |\n"
        f"| **Contract SHA-256** | `{good_hash}` |\n"
        "## Overview\n## Public Surface\n## Contract & Routing\n"
        "## Accessibility & Known Gaps\n## Verification\n"
    )
    (docs_dir / "modules" / "_template.md").write_text(template_body, encoding="utf-8")

    # Write a module doc with a stale hash and missing "## Verification"
    (docs_dir / "modules" / "convert.md").write_text(
        "# Convert\n"
        "| Field | Value |\n|---|---|\n"
        "| **Contract Schema** | `contracts/schemas/capability/system.json` |\n"
        f"| **Contract SHA-256** | `{stale_hash}` |\n"
        "## Overview\n## Public Surface\n## Contract & Routing\n"
        "## Accessibility & Known Gaps\n",
        encoding="utf-8",
    )

    errors = validate_docs_spine(tmp_path)
    assert any("stale Contract SHA-256" in e for e in errors)
    assert any("missing required section '## Verification'" in e for e in errors)
