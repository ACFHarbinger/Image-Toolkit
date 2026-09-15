"""TLA+ state-space model for formal verification (Track B Phase 9, #401).

Models the core concepts of TLA+ specification and model checking in pure
Python — no TLA+ Toolbox or TLC dependency. The model supports:

- ``TLAState``: a named state in the finite state machine, carrying
  variable bindings and optional metadata.
- ``TLATransition``: a labeled edge between states (an action in TLA+ terms).
- ``TLASpec``: a specification = an initial-state predicate + a set of
  transitions (the next-state relation) + invariants (safety/liveness).
- ``StateSpaceGraph``: the explored state space, with bounded BFS model
  checking, invariant checking, and property-violation detection.

The model checker is a bounded BFS over the finite state machine — the
same approach TLC uses, minus the TLA+ parser and the TLC runtime.
Specifications are defined programmatically (not parsed from .tla files),
matching the "research prototype, not v1" scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple

VariableBinding = Dict[str, Any]


@dataclass(frozen=True)
class TLAState:
    """A state in the finite state machine.

    ``variables`` is a frozenset of (name, value) pairs so the state is
    hashable and can be stored in the visited set of the model checker.
    """

    label: str
    variables: FrozenSet[Tuple[str, Any]] = frozenset()

    @classmethod
    def from_dict(cls, label: str, bindings: VariableBinding) -> "TLAState":
        return cls(label=label, variables=frozenset(bindings.items()))

    def binding(self) -> VariableBinding:
        return dict(self.variables)

    def get(self, name: str, default: Any = None) -> Any:
        for k, v in self.variables:
            if k == name:
                return v
        return default

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v}" for k, v in sorted(self.variables))
        return f"{self.label}({items})"


@dataclass(frozen=True)
class TLATransition:
    """A labeled transition (action) between states."""

    label: str  # action name
    source: TLAState
    target: TLAState
    guard: Optional[str] = None  # human-readable guard condition

    def __repr__(self) -> str:
        return f"{self.source} --{self.label}--> {self.target}"


InvariantCheck = Callable[[TLAState], bool]
NextStateRelation = Callable[[TLAState], List[Tuple[str, TLAState]]]


@dataclass
class TLASpec:
    """A TLA+ specification: init + next-state + invariants.

    Defined programmatically (not parsed from .tla). The ``init`` function
    returns the initial states; ``next`` computes successor states for a
    given state; ``invariants`` are safety properties checked at every state.
    """

    name: str
    init: Callable[[], List[TLAState]]
    next: NextStateRelation
    invariants: List[Tuple[str, InvariantCheck]] = field(default_factory=list)

    def add_invariant(self, name: str, check: InvariantCheck) -> None:
        self.invariants.append((name, check))


@dataclass
class PropertyViolation:
    """A detected violation of an invariant or liveness property."""

    state: TLAState
    invariant_name: str
    description: str
    trace: List[TLAState]

    def __repr__(self) -> str:
        path = " -> ".join(s.label for s in self.trace)
        return f"Violation({self.invariant_name} at {self.state}; trace: {path})"


@dataclass
class StateSpaceGraph:
    """The explored state space from model checking a ``TLASpec``.

    Built by ``model_check`` via bounded BFS. Stores all visited states,
    transitions, and any invariant violations found.
    """

    spec_name: str
    states: List[TLAState] = field(default_factory=list)
    transitions: List[TLATransition] = field(default_factory=list)
    state_set: Set[TLAState] = field(default_factory=set)
    violations: List[PropertyViolation] = field(default_factory=list)
    max_depth_reached: int = 0
    total_transitions_explored: int = 0

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def state_count(self) -> int:
        return len(self.states)

    @property
    def transition_count(self) -> int:
        return len(self.transitions)

    def to_tree(self, fold_threshold: int = 5) -> Dict[str, Any]:
        """Render the state space as a tree (ModelWisdom-style structuring).

        Groups states by their tree level (BFS depth) and folds subtrees
        with more than ``fold_threshold`` children into a single collapsed
        node — the same approach ModelWisdom uses for large state spaces.
        """
        if not self.states:
            return {"name": "(empty)", "children": []}

        # Build adjacency from transitions
        children_map: Dict[str, List[TLAState]] = {}
        for t in self.transitions:
            children_map.setdefault(t.source.label, []).append(t.target)

        visited: Set[str] = set()

        def _build_node(state: TLAState) -> Dict[str, Any]:
            if state.label in visited:
                return {"name": state.label, "folded": True}
            visited.add(state.label)
            kids = children_map.get(state.label, [])
            if len(kids) > fold_threshold:
                return {
                    "name": state.label,
                    "folded": True,
                    "child_count": len(kids),
                }
            return {
                "name": state.label,
                "children": [_build_node(c) for c in kids if c.label not in visited],
            }

        root = self.states[0]
        return _build_node(root)


def model_check(
    spec: TLASpec,
    max_depth: int = 50,
    max_states: int = 10000,
) -> StateSpaceGraph:
    """Bounded BFS model checking of a ``TLASpec``.

    Explores the state space up to ``max_depth`` levels deep or
    ``max_states`` total states, checking invariants at every state.
    Returns a ``StateSpaceGraph`` with all visited states, transitions,
    and any invariant violations found.
    """
    graph = StateSpaceGraph(spec_name=spec.name)
    queue: List[Tuple[TLAState, int, List[TLAState]]] = []

    for init_state in spec.init():
        if init_state not in graph.state_set:
            graph.state_set.add(init_state)
            graph.states.append(init_state)
            queue.append((init_state, 0, [init_state]))

    while queue:
        state, depth, trace = queue.pop(0)
        graph.max_depth_reached = max(graph.max_depth_reached, depth)

        # Check invariants
        for inv_name, inv_check in spec.invariants:
            if not inv_check(state):
                graph.violations.append(PropertyViolation(
                    state=state,
                    invariant_name=inv_name,
                    description=f"Invariant {inv_name!r} violated at state {state}",
                    trace=list(trace),
                ))

        if depth >= max_depth or len(graph.states) >= max_states:
            continue

        # Explore successors
        successors = spec.next(state)
        graph.total_transitions_explored += len(successors)
        for action_label, target in successors:
            transition = TLATransition(
                label=action_label,
                source=state,
                target=target,
            )
            graph.transitions.append(transition)

            if target not in graph.state_set:
                graph.state_set.add(target)
                graph.states.append(target)
                queue.append((target, depth + 1, trace + [target]))

    return graph


__all__ = [
    "InvariantCheck",
    "NextStateRelation",
    "PropertyViolation",
    "StateSpaceGraph",
    "TLAState",
    "TLASpec",
    "TLATransition",
    "TLAState",
    "VariableBinding",
    "model_check",
]
