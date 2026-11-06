"""Ground-Rule #1 yield reference as a protocol, not one unseeded run.

refs #654. ``AnimeStitchPipeline.run()`` is not seed-fixed unless
``ASP_DETERMINISTIC=1``. The 2026-09-17 full-97 pair tied the 2026-08-31
RAW_ASP *count* (18) while swapping 9 datasets in and 9 out, and a same-day
rerun moved gate families. ``configure_reproducibility()`` already pins
Python, NumPy, OpenCV, and Torch when that flag is set. Benchmark recipes
default it on, with seed 42, ``PYTHONHASHSEED=42``, and
``CUBLAS_WORKSPACE_CONFIG=:4096:8``. Three reruns of the nine flaky cases
matched ``result_identity`` and ``fallback_reason`` exactly under that
protocol. A full-97 pair under the same protocol has not been recorded
(the 2026-10-02 attempt stopped on the host RAM guardrail).

``torch.use_deterministic_algorithms(True, warn_only=True)`` still lets
some kernels vary, and ``CUBLAS_WORKSPACE_CONFIG`` / ``PYTHONHASHSEED``
must be set before the process starts. Those two facts are why a single
JSON file is not a fixed reference even after the flag is on, until two
full-97 passes compare exact.

Acceptance for a new checkpoint under the benchmark protocol is
:data:`EXACT_DETERMINISTIC_BAND` (no RAW_ASP membership change, no gate
family change). :data:`UNSEEDED_FULL97_20260917_BAND` only describes that
one unseeded pair. It is not a pass band for a code change: an 18-name
swap would hide a real regression.

The flag stays off on the product path. It pins intra-op threads to 1 and
turns cuDNN autotune off, which is the right cost for a reference run and
the wrong default for the GUI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Shell defaults in tools/benchmark/justfile. Caller overrides are preserved
# there; these are the values a Ground-Rule comparison assumes.
REFERENCE_PROTOCOL_ENV: dict[str, str] = {
    "ASP_DETERMINISTIC": "1",
    "ASP_REPRO_SEED": "42",
    "PYTHONHASHSEED": "42",
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
}

# just asp-benchmark-verify (tools/benchmark/justfile).
VERIFY_DATASETS: tuple[str, ...] = (
    "asp_test04",
    "asp_test08",
    "asp_test09",
    "asp_test27",
    "asp_test57",
)

# 2026-09-17 unseeded full-97 vs the 2026-08-31 reference. Count tied at 18.
# These names are the evidence behind UNSEEDED_FULL97_20260917_BAND, not a
# fixture the pipeline special-cases.
UNSEEDED_RAW_ASP_LOST: tuple[str, ...] = (
    "asp_test22",
    "asp_test31",
    "asp_test33",
    "asp_test35",
    "asp_test38",
    "asp_test62",
    "asp_test67",
    "asp_test87",
    "asp_test88",
)
UNSEEDED_RAW_ASP_GAINED: tuple[str, ...] = (
    "asp_test27",
    "asp_test45",
    "asp_test52",
    "asp_test68",
    "asp_test69",
    "asp_test72",
    "asp_test81",
    "asp_test91",
    "asp_test95",
)


@dataclass(frozen=True)
class CaseOutcome:
    """One dataset's benchmark identity and fallback gate string."""

    name: str
    identity: str
    fallback_reason: str | None = None

    @property
    def raw_asp(self) -> bool:
        return self.identity.strip().lower() == "raw_asp"

    @property
    def gate_prefix(self) -> str | None:
        if not self.fallback_reason:
            return None
        return self.fallback_reason.split(":", 1)[0]


@dataclass(frozen=True)
class YieldBand:
    """Limits for one checkpoint pair. Unmatched dataset names fail every band."""

    name: str
    max_raw_asp_symmetric_difference: int
    max_raw_asp_count_delta: int
    max_gate_prefix_changes: int | None = 0


# Required once both runs used REFERENCE_PROTOCOL_ENV. The 9-case audit
# matched fallback strings to the decimal; the prefix check is the part a
# gate-family swap (affine_invalid vs seam_vis_gate) fails.
EXACT_DETERMINISTIC_BAND = YieldBand(
    name="exact_deterministic",
    max_raw_asp_symmetric_difference=0,
    max_raw_asp_count_delta=0,
    max_gate_prefix_changes=0,
)

# Descriptive noise floor of the unseeded 2026-09-17 pair only.
# max_gate_prefix_changes is None because that pair was not counted
# corpus-wide; individual gate swaps were observed on the rerun.
UNSEEDED_FULL97_20260917_BAND = YieldBand(
    name="unseeded_full97_20260917",
    max_raw_asp_symmetric_difference=len(UNSEEDED_RAW_ASP_LOST) + len(UNSEEDED_RAW_ASP_GAINED),
    max_raw_asp_count_delta=0,
    max_gate_prefix_changes=None,
)


@dataclass(frozen=True)
class YieldComparison:
    n_shared: int
    raw_asp_a: int
    raw_asp_b: int
    raw_asp_symmetric_difference: int
    gained_raw_asp: tuple[str, ...]
    lost_raw_asp: tuple[str, ...]
    identity_flips: tuple[str, ...]
    gate_prefix_changes: tuple[str, ...]
    only_in_a: tuple[str, ...]
    only_in_b: tuple[str, ...]

    @property
    def raw_asp_count_delta(self) -> int:
        return abs(self.raw_asp_a - self.raw_asp_b)


@dataclass(frozen=True)
class ReferenceStatus:
    """Whether a pair may stand in for a fixed Ground-Rule #1 reference."""

    exact: bool
    matches_unseeded_noise_floor: bool
    accept_as_deterministic_reference: bool


def _identity_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) and hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _reason_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def case_from_mapping(row: Mapping[str, Any]) -> CaseOutcome | None:
    name = row.get("name") or row.get("dataset")
    if not name:
        return None
    identity = row.get("result_identity", row.get("identity"))
    return CaseOutcome(
        name=str(name),
        identity=_identity_text(identity),
        fallback_reason=_reason_text(row.get("fallback_reason")),
    )


def outcomes_from_run_document(doc: Any) -> dict[str, CaseOutcome]:
    """Read a bench JSON object, a consolidated merge, or a bare dataset list."""
    rows: Any
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, Mapping):
        rows = doc.get("datasets", doc.get("results"))
    else:
        raise TypeError(f"unsupported run document type: {type(doc).__name__}")
    if not isinstance(rows, list):
        raise ValueError("run document has no dataset list")
    out: dict[str, CaseOutcome] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        case = case_from_mapping(row)
        if case is not None:
            out[case.name] = case
    return out


def load_outcomes(path: str | Path) -> dict[str, CaseOutcome]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return outcomes_from_run_document(payload)


def compare_outcomes(
    run_a: Mapping[str, CaseOutcome],
    run_b: Mapping[str, CaseOutcome],
) -> YieldComparison:
    """Diff two identity maps. ``lost_raw_asp`` are raw in A and not in B."""
    only_a = tuple(sorted(set(run_a) - set(run_b)))
    only_b = tuple(sorted(set(run_b) - set(run_a)))
    shared = sorted(set(run_a) & set(run_b))
    gained: list[str] = []
    lost: list[str] = []
    flips: list[str] = []
    gates: list[str] = []
    for name in shared:
        left = run_a[name]
        right = run_b[name]
        if left.raw_asp and not right.raw_asp:
            lost.append(name)
        elif right.raw_asp and not left.raw_asp:
            gained.append(name)
        if left.identity.strip().lower() != right.identity.strip().lower():
            flips.append(name)
        if left.gate_prefix != right.gate_prefix:
            gates.append(name)
    return YieldComparison(
        n_shared=len(shared),
        raw_asp_a=sum(1 for case in run_a.values() if case.raw_asp),
        raw_asp_b=sum(1 for case in run_b.values() if case.raw_asp),
        raw_asp_symmetric_difference=len(gained) + len(lost),
        gained_raw_asp=tuple(gained),
        lost_raw_asp=tuple(lost),
        identity_flips=tuple(flips),
        gate_prefix_changes=tuple(gates),
        only_in_a=only_a,
        only_in_b=only_b,
    )


def within_band(comparison: YieldComparison, band: YieldBand) -> bool:
    names_match = not comparison.only_in_a and not comparison.only_in_b
    raw_ok = (
        comparison.raw_asp_symmetric_difference <= band.max_raw_asp_symmetric_difference
        and comparison.raw_asp_count_delta <= band.max_raw_asp_count_delta
    )
    gate_ok = band.max_gate_prefix_changes is None or (
        len(comparison.gate_prefix_changes) <= band.max_gate_prefix_changes
    )
    return names_match and raw_ok and gate_ok


def reference_status(comparison: YieldComparison) -> ReferenceStatus:
    exact = within_band(comparison, EXACT_DETERMINISTIC_BAND)
    noise = within_band(comparison, UNSEEDED_FULL97_20260917_BAND)
    return ReferenceStatus(
        exact=exact,
        matches_unseeded_noise_floor=noise,
        accept_as_deterministic_reference=exact,
    )


def format_reference_status(comparison: YieldComparison, status: ReferenceStatus) -> str:
    lines = [
        f"shared={comparison.n_shared} raw_asp {comparison.raw_asp_a} -> {comparison.raw_asp_b} "
        f"(delta {comparison.raw_asp_count_delta})",
        f"raw_asp_symmetric_difference={comparison.raw_asp_symmetric_difference} "
        f"gained={list(comparison.gained_raw_asp)} lost={list(comparison.lost_raw_asp)}",
        f"identity_flips={list(comparison.identity_flips)} "
        f"gate_prefix_changes={list(comparison.gate_prefix_changes)}",
        f"only_in_a={list(comparison.only_in_a)} only_in_b={list(comparison.only_in_b)}",
        f"exact={status.exact} unseeded_noise_floor={status.matches_unseeded_noise_floor} "
        f"accept_as_deterministic_reference={status.accept_as_deterministic_reference}",
        "Deterministic reference protocol: "
        + " ".join(f"{key}={value}" for key, value in REFERENCE_PROTOCOL_ENV.items()),
    ]
    return "\n".join(lines)


def compare_run_files(path_a: str | Path, path_b: str | Path) -> tuple[YieldComparison, ReferenceStatus]:
    comparison = compare_outcomes(load_outcomes(path_a), load_outcomes(path_b))
    return comparison, reference_status(comparison)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two ASP benchmark JSON runs. Exit 0 only when the pair "
            "is an exact deterministic reference (refs #654)."
        )
    )
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    args = parser.parse_args(list(argv) if argv is not None else None)
    comparison, status = compare_run_files(args.run_a, args.run_b)
    print(format_reference_status(comparison, status))
    return 0 if status.accept_as_deterministic_reference else 1


if __name__ == "__main__":
    sys.exit(main())
