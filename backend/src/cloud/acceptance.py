"""The only thing the engine will enqueue: a job that passed preflight (Gate A review blocker 1).

:class:`AcceptedJob` binds the *sanitized* spec, the acknowledgements given,
the secret decisions and the cost reservation to execution. It can only be
built through :func:`issue`, which the submission service calls after
``run_preflight`` passed; the engine rejects anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from .spec import JobSpec

_ISSUER = object()


class NotAccepted(TypeError):
    """Raised when something tries to enqueue a job that did not pass preflight."""


@dataclass(frozen=True)
class AcceptedJob:
    spec: JobSpec
    reservation_usd: float
    capability_override: bool
    acknowledged: Tuple[str, ...]
    secret_decisions: Tuple[Tuple[str, str, str], ...] = ()  # (node_id, field, keep|strip)
    estimate: Mapping[str, float] = field(default_factory=dict)
    price_rows: Tuple[Dict[str, Any], ...] = ()
    _issuer: object = field(default=None, repr=False, compare=False)

    def check(self) -> None:
        if self._issuer is not _ISSUER:
            raise NotAccepted("submit through CloudJobService.submit(), which runs preflight first")

    def record(self) -> Dict[str, Any]:
        """What the store keeps, so revalidation reuses the same acknowledgements and choices."""
        return {
            "reservation_usd": self.reservation_usd,
            "capability_override": self.capability_override,
            "acknowledged": list(self.acknowledged),
            "secret_decisions": [list(d) for d in self.secret_decisions],
            "estimate": dict(self.estimate),
            "price_rows": list(self.price_rows),
        }


def issue(spec: JobSpec, reservation_usd: float, capability_override: bool, acknowledged: Tuple[str, ...],
          secret_decisions: Tuple[Tuple[str, str, str], ...] = (), estimate: Mapping[str, float] = None,
          price_rows: Tuple[Dict[str, Any], ...] = ()) -> AcceptedJob:
    """Call only after preflight passed. Tests that exercise the engine alone use ``fakes.accept_unchecked``."""
    return AcceptedJob(spec, reservation_usd, capability_override, tuple(acknowledged), tuple(secret_decisions),
                       dict(estimate or {}), tuple(price_rows), _ISSUER)
