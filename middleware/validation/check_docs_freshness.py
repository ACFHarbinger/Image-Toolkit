"""Validate documentation spine freshness (W0-21 / Issue #885).

Enforces:
1. `docs/ARCHITECTURE.md` (with C4 diagrams) and `docs/ASP_ARCHITECTURE.md` exist.
2. `docs/adr/` contains `index.md` plus every numbered ADR linked from `index.md`.
3. Every module README in `docs/modules/*.md` carries:
   - a valid `Contract Schema` path present in `contracts/CONTRACTS.sha256`
     (or `contracts/CONTRACTS.sha256` itself for the `total` hash);
   - a `Contract SHA-256` value matching the live digest in `contracts/CONTRACTS.sha256`;
   - the required sections (`## Overview`, `## Public Surface`, `## Contract & Routing`,
     `## Accessibility & Known Gaps`, `## Verification`) for concrete module docs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_MODULE_SECTIONS = (
    "## Overview",
    "## Public Surface",
    "## Contract & Routing",
    "## Accessibility & Known Gaps",
    "## Verification",
)

SCHEMA_FIELD_RE = re.compile(
    r"\|\s*\*\*Contract Schema\*\*\s*\|\s*`([^`]+)`",
    re.MULTILINE,
)
HASH_FIELD_RE = re.compile(
    r"\|\s*\*\*Contract SHA-256\*\*\s*\|\s*`([0-9a-f]{64})`",
    re.MULTILINE,
)
ADR_LINK_RE = re.compile(r"\[ADR-\d{4}\]\(([^)]+\.md)\)")


def parse_contracts_sha256(contracts_sha_file: Path) -> dict[str, str]:
    """Return mapping of `{target_path_or_total: sha256_hex}` from `CONTRACTS.sha256`."""
    mapping: dict[str, str] = {}
    for raw_line in contracts_sha_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("//", "#")):
            continue
        parts = line.split()
        if len(parts) == 2:
            left, right = parts
            if left == "total" and re.fullmatch(r"[0-9a-f]{64}", right):
                mapping["total"] = right
                mapping["contracts/CONTRACTS.sha256"] = right
            elif re.fullmatch(r"[0-9a-f]{64}", left):
                mapping[right] = left
    return mapping


def _validate_architecture_docs(repo_root: Path) -> list[str]:
    errors: list[str] = []
    arch_file = repo_root / "docs" / "ARCHITECTURE.md"
    asp_arch_file = repo_root / "docs" / "ASP_ARCHITECTURE.md"
    if not arch_file.is_file():
        errors.append("Missing docs/ARCHITECTURE.md")
    else:
        arch_text = arch_file.read_text(encoding="utf-8")
        for level in ("C4 Level 1", "C4 Level 2", "C4 Level 3"):
            if level not in arch_text:
                errors.append(f"docs/ARCHITECTURE.md is missing C4 section: {level}")
    if not asp_arch_file.is_file():
        errors.append("Missing docs/ASP_ARCHITECTURE.md (renamed ASP stitching reference)")
    return errors


def _validate_adrs(repo_root: Path) -> list[str]:
    errors: list[str] = []
    adr_dir = repo_root / "docs" / "adr"
    adr_index = adr_dir / "index.md"
    if not adr_index.is_file():
        return ["Missing docs/adr/index.md"]

    index_text = adr_index.read_text(encoding="utf-8")
    linked_adrs = ADR_LINK_RE.findall(index_text)
    if not linked_adrs:
        errors.append("docs/adr/index.md does not link any ADR files")
    for rel_adr in linked_adrs:
        if not (adr_dir / rel_adr).is_file():
            errors.append(f"docs/adr/index.md links missing ADR: {rel_adr}")

    actual_adrs = {p.name for p in adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")}
    for name in sorted(actual_adrs - set(linked_adrs)):
        errors.append(f"ADR file is not indexed in docs/adr/index.md: {name}")
    return errors


def _validate_module_file(
    md_file: Path, repo_root: Path, contract_hashes: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    text = md_file.read_text(encoding="utf-8")
    rel_md = md_file.relative_to(repo_root).as_posix()

    schema_match = SCHEMA_FIELD_RE.search(text)
    hash_match = HASH_FIELD_RE.search(text)
    if not schema_match:
        errors.append(f"{rel_md}: missing '| **Contract Schema** | `<path>` |' metadata row")
    if not hash_match:
        errors.append(f"{rel_md}: missing '| **Contract SHA-256** | `<64-hex>` |' metadata row")

    if schema_match and hash_match:
        schema_key = schema_match.group(1).strip()
        recorded_hash = hash_match.group(1).strip()
        expected_hash = contract_hashes.get(schema_key)
        if expected_hash is None:
            errors.append(
                f"{rel_md}: Contract Schema '{schema_key}' not found in contracts/CONTRACTS.sha256"
            )
        elif recorded_hash != expected_hash:
            errors.append(
                f"{rel_md}: stale Contract SHA-256 for '{schema_key}': "
                f"doc has {recorded_hash}, CONTRACTS.sha256 has {expected_hash}"
            )

    for section in REQUIRED_MODULE_SECTIONS:
        if section not in text:
            errors.append(f"{rel_md}: missing required section '{section}'")
    return errors


def validate_docs_spine(repo_root: Path) -> list[str]:
    """Validate the W0-21 documentation spine and return a list of errors."""
    contracts_sha_file = repo_root / "contracts" / "CONTRACTS.sha256"
    if not contracts_sha_file.is_file():
        return [f"Missing contract hash manifest: {contracts_sha_file}"]

    errors: list[str] = []
    contract_hashes = parse_contracts_sha256(contracts_sha_file)
    if "total" not in contract_hashes:
        errors.append("contracts/CONTRACTS.sha256 is missing the 'total' digest line.")

    errors.extend(_validate_architecture_docs(repo_root))
    errors.extend(_validate_adrs(repo_root))

    modules_dir = repo_root / "docs" / "modules"
    if not modules_dir.is_dir():
        errors.append("Missing docs/modules/ directory")
        return errors

    if not (modules_dir / "_template.md").is_file():
        errors.append("Missing docs/modules/_template.md")

    module_files = sorted(p for p in modules_dir.glob("*.md") if p.name != "index.md")
    if not module_files:
        errors.append("No module documentation files found in docs/modules/")

    for md_file in module_files:
        errors.extend(_validate_module_file(md_file, repo_root, contract_hashes))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check W0-21 documentation spine freshness.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root directory",
    )
    args = parser.parse_args(argv)

    errors = validate_docs_spine(args.root.resolve())
    if errors:
        for err in errors:
            print(f"[docs-freshness] ERROR: {err}", file=sys.stderr)
        return 1

    print("[docs-freshness] OK: ADR spine, C4 architecture, and module contract hashes are fresh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
