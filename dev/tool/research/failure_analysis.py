"""#396: dependency measures over existing host evidence.

This deliberately accepts decoded JSONL/Parquet rows supplied by the host;
it does not define another telemetry export format or claim causality.
"""

from __future__ import annotations

from collections import Counter
from math import log2
from typing import Any, Iterable, Mapping


def _values(rows: Iterable[Mapping[str, Any]], key: str) -> list[str]:
    return [str(row[key]) for row in rows if row.get(key) is not None]


def shannon_entropy(values: Iterable[object]) -> float:
    """Return Shannon entropy in bits; empty and constant samples are zero."""
    counts = Counter(map(str, values))
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((n / total) * log2(n / total) for n in counts.values())


def mutual_information(rows: Iterable[Mapping[str, Any]], left: str, right: str) -> float:
    """Empirical MI in bits for rows having both dimensions."""
    pairs = [(str(row[left]), str(row[right])) for row in rows if row.get(left) is not None and row.get(right) is not None]
    total = len(pairs)
    if not total:
        return 0.0
    joint, lefts, rights = Counter(pairs), Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    return sum((n / total) * log2((n * total) / (lefts[a] * rights[b])) for (a, b), n in joint.items())


def kl_divergence(baseline: Iterable[object], observed: Iterable[object]) -> float:
    """KL(observed || baseline), with unseen baseline values reported as infinity."""
    base, obs = Counter(map(str, baseline)), Counter(map(str, observed))
    base_total, obs_total = sum(base.values()), sum(obs.values())
    if not obs_total:
        return 0.0
    if not base_total or any(value not in base for value in obs):
        return float("inf")
    return sum((n / obs_total) * log2((n / obs_total) / (base[value] / base_total)) for value, n in obs.items())


def failure_profile(rows: Iterable[Mapping[str, Any]], dimension: str, outcome: str = "outcome", failed: str = "failure") -> dict[str, float]:
    """Likelihood lift for each categorical value; descriptive, never causal."""
    data = list(rows)
    all_values, failed_values = _values(data, dimension), _values((row for row in data if str(row.get(outcome)) == failed), dimension)
    if not all_values or not failed_values:
        return {}
    overall = len(failed_values) / len(all_values)
    return {value: (failed_values.count(value) / all_values.count(value)) / overall for value in sorted(set(failed_values))}
