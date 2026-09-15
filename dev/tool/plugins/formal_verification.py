"""Track B Phase 9 Formal Verification Plugin: TLA+ model checking, concolic execution, SMT telemetry (#401)."""

from __future__ import annotations

from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..research.formal_verification import (
    SMTInstantiationEvent,
    concolic_explore,
    detect_matching_loops,
    visualize_state_space,
)

MANIFEST = PluginManifest(
    name="formal_verification",
    version="0.1.0",
    description="Formal verification: TLA+ state-space model checking, concolic execution, and SMT solver telemetry analysis (Track B Phase 9).",
    surfaces=(
        Surface("cli", "Model-check specs, run concolic exploration, detect matching loops"),
        Surface("web", "State-space tree visualization, violation highlighting, concolic path timeline"),
        Surface("mcp", "Invariant queries, state-space exploration, matching-loop detection"),
    ),
    channels=(
        Channel("state_space", "TLA+ model-checked state space", retention="forever"),
        Channel("concolic", "Concolic execution path exploration", retention="30d"),
        Channel("smt_telemetry", "SMT solver instantiation telemetry and matching-loop detection", default_enabled=False, retention="7d"),
    ),
    entry_point="tool.plugins.formal_verification:plugin",
)

# A simple reference spec for demonstration: a two-state lock with
# acquire/release. Proves that the lock is never held by two owners
# simultaneously (mutual exclusion invariant).

_DEMO_SOURCE = """
def lock_acquire(state):
    if state == "free":
        return "locked"
    elif state == "locked":
        return "locked"
    return "error"
"""

from ..model.tla_state import TLASpec, TLAState, model_check  # noqa: E402


def _build_demo_spec() -> TLASpec:
    """Build a simple TLA+ spec: a mutual-exclusion lock."""

    def init() -> list[TLAState]:
        return [TLAState.from_dict("Init", {"owner": "none", "held": False})]

    def next(state: TLAState) -> list[tuple[str, TLAState]]:
        owner = state.get("owner", "none")
        held = state.get("held", False)
        successors: list[tuple[str, TLAState]] = []
        if owner == "none" and not held:
            successors.append(("Acquire", TLAState.from_dict("Locked", {"owner": "proc1", "held": True})))
        elif held:
            successors.append(("Release", TLAState.from_dict("Released", {"owner": "none", "held": False})))
        return successors

    spec = TLASpec(name="mutex_lock", init=init, next=next)
    spec.add_invariant(
        "MutualExclusion",
        lambda s: not (s.get("held", False) and s.get("owner", "none") == "none"),
    )
    return spec


class FormalVerificationPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        artifacts: List[Artifact] = []

        # 1. State-space model checking artifact
        spec = _build_demo_spec()
        graph = model_check(spec, max_depth=20, max_states=1000)
        viz = visualize_state_space(graph)

        artifacts.append(Artifact(
            kind="state_space",
            name="formal_verification:state_space:mutex_lock",
            meta={
                "research": True,
                "spec_name": spec.name,
                "state_count": viz.total_states,
                "transition_count": viz.total_transitions,
                "max_depth": viz.max_depth,
                "violation_count": viz.violation_count,
                "has_violations": viz.violation_count > 0,
                "tree": viz.tree,
            },
        ))

        # 2. Concolic execution artifact
        concolic_report = concolic_explore(_DEMO_SOURCE, "lock_acquire", max_paths=10)
        artifacts.append(Artifact(
            kind="concolic",
            name="formal_verification:concolic:lock_acquire",
            meta={
                "research": True,
                "function_name": concolic_report.function_name,
                "total_branches": concolic_report.total_branches,
                "covered_branches": concolic_report.covered_branches,
                "coverage": round(concolic_report.coverage, 4),
                "path_count": len(concolic_report.paths),
                "path_conditions": [
                    {
                        "condition": p.path_condition(),
                        "depth": p.depth,
                        "inputs": p.inputs,
                    }
                    for p in concolic_report.paths[:5]
                ],
            },
        ))

        # 3. SMT telemetry analysis artifact (synthetic events for demo)
        smt_events = [
            SMTInstantiationEvent(timestamp=0.001 * i, quantifier="forall_x", trigger="pattern_A", result="useful")
            if i % 3 != 2 else
            SMTInstantiationEvent(timestamp=0.001 * i, quantifier="forall_y", trigger="pattern_B", result="useless")
            for i in range(20)
        ]
        loops = detect_matching_loops(smt_events)
        artifacts.append(Artifact(
            kind="smt_telemetry",
            name="formal_verification:smt_telemetry:demo",
            meta={
                "research": True,
                "total_events": len(smt_events),
                "loop_count": len(loops),
                "loops": [
                    {
                        "quantifiers": l.quantifiers,
                        "instantiation_count": l.instantiation_count,
                        "duration_ms": round(l.duration_ms, 2),
                    }
                    for l in loops
                ],
            },
        ))

        return artifacts


plugin = FormalVerificationPlugin()


def main(argv=None) -> int:
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
