"""Unit tests for Track B Phase 9: Formal Verification & State Space Visualization (#401)."""

from __future__ import annotations

from pathlib import Path

from tool.host import discover_plugins
from tool.host.store import WorkspaceStore
from tool.model.tla_state import (
    PropertyViolation,
    StateSpaceGraph,
    TLASpec,
    TLAState,
    TLATransition,
    model_check,
)
from tool.research.formal_verification import (
    ConcolicPath,
    PathConstraint,
    SMTInstantiationEvent,
    concolic_explore,
    detect_matching_loops,
    sonify_instantiation_events,
    visualize_state_space,
)

# ---------------------------------------------------------------------------
# TLA+ state-space model
# ---------------------------------------------------------------------------

def test_tla_state_creation():
    s = TLAState.from_dict("Init", {"owner": "none", "held": False})
    assert s.label == "Init"
    assert s.get("owner") == "none"
    assert s.get("held") is False
    assert s.get("missing", "default") == "default"


def test_tla_state_hashable():
    s1 = TLAState.from_dict("A", {"x": 1})
    s2 = TLAState.from_dict("A", {"x": 1})
    assert s1 == s2  # frozen dataclass with same fields
    assert hash(s1) == hash(s2)


def test_tla_state_immutable():
    from dataclasses import FrozenInstanceError

    import pytest

    s = TLAState.from_dict("S", {"v": 42})
    with pytest.raises(FrozenInstanceError):
        s.variables = frozenset()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Model checking
# ---------------------------------------------------------------------------

def test_model_check_mutex_no_violation():
    """A well-designed mutex should have no invariant violations."""

    def init():
        return [TLAState.from_dict("Init", {"owner": "none", "held": False})]

    def next(state):
        owner = state.get("owner", "none")
        held = state.get("held", False)
        if owner == "none" and not held:
            return [("Acquire", TLAState.from_dict("Locked", {"owner": "p1", "held": True}))]
        if held:
            return [("Release", TLAState.from_dict("Released", {"owner": "none", "held": False}))]
        return []

    spec = TLASpec(name="mutex", init=init, next=next)
    spec.add_invariant("MutualExclusion", lambda s: not (s.get("held", False) and s.get("owner") == "none"))

    graph = model_check(spec, max_depth=10)
    assert graph.state_count >= 3  # Init, Locked, Released
    assert not graph.has_violations
    assert graph.max_depth_reached >= 1


def test_model_check_detects_violation():
    """An intentionally broken spec should detect invariant violations."""

    def init():
        return [TLAState.from_dict("S0", {"x": 0})]

    def next(state):
        x = state.get("x", 0)
        return [("Inc", TLAState.from_dict(f"S{x+1}", {"x": x + 1}))]

    spec = TLASpec(name="counter", init=init, next=next)
    # Invariant: x must never exceed 2 — will be violated
    spec.add_invariant("MaxTwo", lambda s: s.get("x", 0) <= 2)

    graph = model_check(spec, max_depth=10)
    assert graph.has_violations
    assert len(graph.violations) >= 1
    v = graph.violations[0]
    assert v.invariant_name == "MaxTwo"
    assert len(v.trace) >= 3  # Init -> S1 -> S2 -> S3 (violation)


def test_model_check_bounds():
    """max_depth and max_states should bound exploration."""

    def init():
        return [TLAState.from_dict("S0", {"n": 0})]

    def next(state):
        n = state.get("n", 0)
        return [("Inc", TLAState.from_dict(f"S{n+1}", {"n": n + 1}))]

    spec = TLASpec(name="unbounded", init=init, next=next)
    graph = model_check(spec, max_depth=3, max_states=5)
    assert graph.state_count <= 5
    assert graph.max_depth_reached <= 3


# ---------------------------------------------------------------------------
# State-space visualization
# ---------------------------------------------------------------------------

def test_visualize_state_space():
    graph = StateSpaceGraph(spec_name="test")
    s1 = TLAState.from_dict("A", {"x": 1})
    s2 = TLAState.from_dict("B", {"x": 2})
    graph.states = [s1, s2]
    graph.state_set = {s1, s2}
    graph.transitions = [TLATransition(label="T", source=s1, target=s2)]
    graph.violations = []
    graph.max_depth_reached = 1

    viz = visualize_state_space(graph)
    assert viz.total_states == 2
    assert viz.total_transitions == 1
    assert viz.violation_count == 0
    assert "name" in viz.tree


def test_visualize_with_violation():
    graph = StateSpaceGraph(spec_name="test")
    s1 = TLAState.from_dict("A", {"x": 1})
    s2 = TLAState.from_dict("B", {"x": 2})
    graph.states = [s1, s2]
    graph.state_set = {s1, s2}
    graph.transitions = [TLATransition(label="T", source=s1, target=s2)]
    graph.violations = [PropertyViolation(
        state=s2, invariant_name="TestInv",
        description="test violation", trace=[s1, s2],
    )]
    graph.max_depth_reached = 1

    viz = visualize_state_space(graph)
    assert viz.violation_count == 1
    assert len(viz.violations) == 1
    assert viz.violations[0]["invariant"] == "TestInv"
    assert viz.violations[0]["highlight"] is True


# ---------------------------------------------------------------------------
# Concolic execution
# ---------------------------------------------------------------------------

def test_concolic_explore():
    source = """
    def validate(x, y):
        if x > 5:
            return True
        elif y < 0:
            return False
        return None
    """
    report = concolic_explore(source, "validate", max_paths=10)
    assert report.function_name == "validate"
    assert report.total_branches == 4  # 2 if-statements * 2 branches each
    assert len(report.paths) > 0
    assert report.coverage > 0.0

    # Each path should have at least one constraint
    for path in report.paths:
        assert path.depth >= 1
        cond = path.path_condition()
        assert cond != "true"  # at least one constraint


def test_concolic_explore_no_branches():
    source = "def simple():\n    return 42\n"
    report = concolic_explore(source, "simple", max_paths=5)
    assert report.total_branches == 0
    assert report.coverage == 1.0  # no branches to cover


def test_concolic_path_condition():
    pc = PathConstraint(expression="x > 5", branch_taken=True, line=3)
    path = ConcolicPath(inputs={"x": 10}, constraints=[pc])
    assert path.path_condition() == "x > 5"

    pc2 = PathConstraint(expression="y < 0", branch_taken=False, line=5)
    path.constraints.append(pc2)
    assert "!(y < 0)" in path.path_condition()


# ---------------------------------------------------------------------------
# SMT matching-loop detection
# ---------------------------------------------------------------------------

def test_detect_matching_loops():
    # Create a repeating cycle: forall_x -> forall_y -> forall_x -> forall_y ...
    events = []
    for i in range(20):
        q = "forall_x" if i % 2 == 0 else "forall_y"
        events.append(SMTInstantiationEvent(
            timestamp=0.001 * i,
            quantifier=q,
            trigger="pattern_A",
            result="useful",
        ))

    loops = detect_matching_loops(events, min_cycle_length=2, min_instantiations=4)
    assert len(loops) >= 1
    loop = loops[0]
    assert len(loop.quantifiers) >= 2
    assert loop.instantiation_count >= 4


def test_detect_matching_loops_no_loop():
    events = [
        SMTInstantiationEvent(timestamp=0.0 + i, quantifier=f"q_{i}", trigger="t", result="useful")
        for i in range(10)
    ]
    loops = detect_matching_loops(events, min_cycle_length=2, min_instantiations=4)
    assert len(loops) == 0


def test_sonify_events():
    events = [
        SMTInstantiationEvent(timestamp=0.0, quantifier="q", trigger="t", result="useful"),
        SMTInstantiationEvent(timestamp=0.01, quantifier="q", trigger="t", result="useless"),
    ]
    samples = sonify_instantiation_events(events, sample_rate=8000)
    assert len(samples) > 0
    assert all(-1.0 <= s <= 1.0 for s in samples)


def test_sonify_empty():
    assert sonify_instantiation_events([]) == []


# ---------------------------------------------------------------------------
# Plugin discovery and artifacts
# ---------------------------------------------------------------------------

def test_formal_verification_plugin_discovery(tmp_path: Path):
    store = WorkspaceStore(root=tmp_path / "inv", telemetry_dir=tmp_path)
    plugins = {p.manifest.name: p for p in discover_plugins(store)}
    assert "formal_verification" in plugins

    plugin = plugins["formal_verification"]
    artifacts = plugin.artifacts(store)

    kinds = {a.kind for a in artifacts}
    assert "state_space" in kinds
    assert "concolic" in kinds
    assert "smt_telemetry" in kinds

    # Check the state-space artifact
    state_space = next(a for a in artifacts if a.kind == "state_space")
    assert state_space.meta["research"] is True
    assert state_space.meta["spec_name"] == "mutex_lock"
    assert state_space.meta["state_count"] > 0
