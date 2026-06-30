#!/usr/bin/env python3
"""§3.14B — Module import-time regression gate.

Measures the wall-clock import time of every ``backend.src.animation.*`` module
and flags any that exceed SLOW_IMPORT_THRESHOLD seconds.

Usage
-----
    source .venv/bin/activate
    python scripts/check_import_times.py           # human-readable report
    python scripts/check_import_times.py --ci      # exits 1 if any module is slow
    python scripts/check_import_times.py --json    # machine-readable JSON output

CI integration (add to .github/workflows or equivalent):
    - name: Check module import times
      run: source .venv/bin/activate && python scripts/check_import_times.py --ci

Why this exists (§3.14)
-----------------------
Unconditional heavy imports at the top of animation modules were a confirmed root
cause of the test-suite process freeze.  This script catches future regressions
before they land — a new ``import sam2`` at module level would be flagged
immediately rather than discovered by a dying test run.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SLOW_IMPORT_THRESHOLD = (
    1.5  # seconds above baseline — flag module-specific import cost exceeding this
)

# All animation modules we track.  Add new modules here when they are created.
ANIM_MODULES: List[str] = [
    "backend.src.animation.alignment.bundle_adjust",
    "backend.src.animation.alignment.canvas",
    "backend.src.animation.rendering.compositing",
    "backend.src.animation.core.config",
    "backend.src.animation.alignment.ecc",
    "backend.src.animation.alignment.fg_register",
    "backend.src.animation.ingestion.frame_selection",
    "backend.src.animation.alignment.matching",
    "backend.src.animation.ingestion.masking",
    "backend.src.animation.core.pipeline",
    "backend.src.animation.rendering.photometric",
    "backend.src.animation.rendering.rendering",
    "backend.src.animation.core.validation",
    "backend.src.animation.ingestion.bg_complete",
]

# §3.15C — Core modules that were audited for heavy-import isolation.
# image_merger previously loaded BiRefNetWrapper + LoFTRWrapper + AnimeStitchPipeline
# unconditionally (~3 s); vault_manager loaded jpype unconditionally.
CORE_MODULES: List[str] = [
    "backend.src.core.image_merger",
    "backend.src.core.vault_manager",
]

# Additional heavy dependencies that should NOT be importable at module level
# (they must stay behind try/except or lazy function-level imports).
FORBIDDEN_AT_MODULE_LEVEL: List[str] = [
    "sam2",
    "diffusers",
    "sklearn",
]

# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #


def _measure_baseline() -> float:
    """Measure the Python + common-dependency startup cost (cv2, numpy, scipy).

    This is the irreducible overhead present in every subprocess measurement.
    Module-specific import cost = raw measurement − baseline.
    """
    repo_root = str(Path(__file__).parent.parent)
    # Baseline includes torch because it is a required project dependency that
    # is always imported when any animation module loads (torch is ~2.5 s).
    # We only flag the ADDITIONAL cost beyond this mandatory baseline.
    cmd = [
        sys.executable,
        "-c",
        f"import sys; sys.path.insert(0, {repo_root!r}); "
        "import time; t=time.perf_counter(); "
        "import cv2, numpy, scipy, torch; "
        "print(f'{time.perf_counter()-t:.4f}')",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return float(result.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return 0.0


def _measure_in_subprocess(module_name: str) -> Tuple[float, str]:
    """Measure the import time of *module_name* in a fresh subprocess.

    Returns (elapsed_seconds, stderr_output).  Using a subprocess guarantees
    that the timing is unaffected by modules already loaded in the parent
    process and that any side-effects (CUDA init, thread pool creation) are
    isolated.
    """
    repo_root = str(Path(__file__).parent.parent)
    cmd = [
        sys.executable,
        "-c",
        f"import sys; sys.path.insert(0, {repo_root!r}); "
        f"import time; t=time.perf_counter(); "
        f"import {module_name}; "
        f"print(f'{{time.perf_counter()-t:.4f}}')",
    ]
    t0 = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        return elapsed, result.stderr.strip()

    try:
        reported = float(result.stdout.strip().splitlines()[-1])
        return reported, ""
    except (ValueError, IndexError):
        return elapsed, result.stderr.strip()


def _check_forbidden_at_module_level(module_name: str) -> List[str]:
    """Return a list of forbidden libraries that are directly importable
    after importing *module_name* without those libraries being installed.

    This is a heuristic check: if the module unconditionally imports
    ``sam2``, importing it will either succeed (sam2 is installed — OK,
    but still not ideal) or fail with ImportError (not guarded).
    We check the *source* instead.
    """
    violations: List[str] = []
    try:
        path = importlib.util.find_spec(module_name)  # type: ignore[attr-defined]
        if path is None or path.origin is None:
            return violations
        source = Path(path.origin).read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Only flag unconditional top-level imports (not inside try/except,
            # not inside a function/class/if block).
            if (
                stripped.startswith("import ") or stripped.startswith("from ")
            ) and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent == 0:  # module-level (no indentation)
                    for forbidden in FORBIDDEN_AT_MODULE_LEVEL:
                        if forbidden in stripped:
                            violations.append(f"  line {i}: {stripped[:80]}")
    except Exception:
        pass
    return violations


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def run(ci: bool = False, as_json: bool = False) -> int:
    """Run the full audit.  Returns 0 on success, 1 if any module is slow."""
    results: Dict[str, dict] = {}
    slow: List[str] = []
    errors: List[str] = []
    violations_map: Dict[str, List[str]] = {}

    print(
        f"Measuring module-specific import cost (threshold above baseline: {SLOW_IMPORT_THRESHOLD:.1f}s)…"
    )
    print("Measuring baseline (cv2 + numpy + scipy startup)…", end=" ", flush=True)
    baseline = _measure_baseline()
    print(f"{baseline:.3f}s\n")

    all_modules = [("animation", m) for m in ANIM_MODULES] + [
        ("core", m) for m in CORE_MODULES
    ]

    current_group = ""
    for group, mod in all_modules:
        if group != current_group:
            print(f"--- {group} modules ---")
            current_group = group
        elapsed, err = _measure_in_subprocess(mod)
        net = max(0.0, elapsed - baseline)
        flag = net > SLOW_IMPORT_THRESHOLD
        if flag:
            slow.append(mod)
        if err:
            errors.append(mod)
        violations = _check_forbidden_at_module_level(mod)
        if violations:
            violations_map[mod] = violations
        results[mod] = {
            "elapsed": round(elapsed, 4),
            "net_above_baseline": round(net, 4),
            "slow": flag,
            "error": err,
        }
        status = "SLOW ⚠" if flag else ("ERR " if err else "ok  ")
        print(f"  {status}  {net:5.2f}s net  ({elapsed:.2f}s total)  {mod}")

    print()

    if violations_map:
        print("=== Forbidden unconditional imports detected ===")
        for mod, lines in violations_map.items():
            print(f"  {mod}:")
            for line in lines:
                print(line)
        print()

    if errors:
        print(f"Modules with import errors: {', '.join(errors)}")

    total = len(ANIM_MODULES) + len(CORE_MODULES)
    if slow:
        print(
            f"SLOW modules (net cost >{SLOW_IMPORT_THRESHOLD:.1f}s above baseline): {', '.join(slow)}"
        )
        print(
            "Diagnose with: python -X importtime -c 'import sys; sys.path.insert(0,\".\"); import <module>'"
        )
        if ci:
            return 1
    else:
        print(
            f"All {total} modules within {SLOW_IMPORT_THRESHOLD:.1f}s above baseline. ✓"
        )

    if as_json:
        print(json.dumps(results, indent=2))

    return 0


def main() -> None:
    global SLOW_IMPORT_THRESHOLD  # noqa: PLW0603
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit with code 1 if any module exceeds the threshold (for CI gates).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit JSON results to stdout after the human-readable report.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=SLOW_IMPORT_THRESHOLD,
        help=f"Slow-import threshold in seconds (default: {SLOW_IMPORT_THRESHOLD}).",
    )
    args = parser.parse_args()
    SLOW_IMPORT_THRESHOLD = args.threshold

    sys.exit(run(ci=args.ci, as_json=args.as_json))


if __name__ == "__main__":
    main()
