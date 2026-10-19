"""Adapter certification kit (#829): one contract every provider adapter must pass.

Levels: ``declared`` checks the capability manifest only; ``recorded`` runs
the lifecycle contract against recorded HTTP or a fake transport; ``live``
runs the same contract against the real provider (``live_cloud`` marker,
through the benchmark chain: it spends money).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from .adapter import (
    TAG_IDEMPOTENCY,
    TAG_JOB,
    TAG_OWNER,
    AttemptContext,
    ProviderAdapter,
    ProviderStatus,
    find_by_idempotency,
)
from .spec import JobSpec

LEVEL_DECLARED = "declared"
LEVEL_RECORDED = "recorded"
LEVEL_LIVE = "live"
LEVELS = (LEVEL_DECLARED, LEVEL_RECORDED, LEVEL_LIVE)


@dataclass
class CertificationReport:
    adapter: str
    level: str
    passed: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def check(self, name: str, cond: bool, why: str = "") -> None:
        (self.passed.append(name) if cond else self.failed.append((name, why or name)))


def certify(adapter: ProviderAdapter, spec_factory: Callable[[], JobSpec], level: str = LEVEL_RECORDED,
            owner: str = "it-certify", today: _dt.date | None = None) -> CertificationReport:
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    rep = CertificationReport(adapter.name, level)
    man = adapter.capabilities()
    rep.check("manifest.provider_matches", man.provider == adapter.name, f"{man.provider!r} != {adapter.name!r}")
    rep.check("manifest.has_modes", bool(man.modes))
    rep.check("manifest.has_storage", bool(man.storage))
    rep.check("manifest.cpu_only_subset", man.cpu_only_modes <= man.modes)
    if level != LEVEL_DECLARED:
        try:
            verified = _dt.date.fromisoformat(man.verified_on)
            rep.check("manifest.verified_on_recent", ((today or _dt.date.today()) - verified).days <= 180,
                      f"facts last verified {man.verified_on}")
        except ValueError:
            rep.check("manifest.verified_on_recent", False, "verified_on is not an ISO date")
    if level == LEVEL_DECLARED:
        return rep

    spec = spec_factory()
    rep.check("plan.pure", adapter.plan(spec) == adapter.plan(spec))
    ctx = AttemptContext(spec.job_id, f"{spec.job_id}-cert", 1, spec.idempotency_key(1), spec,
                         tuple(s.index for s in spec.shards), owner, 4_102_444_800.0)
    receipt = adapter.submit(ctx)
    rep.check("submit.returns_resources", bool(receipt.resources))
    for r in receipt.resources:
        rep.check(f"submit.tags[{r.resource_id}]",
                  r.tags.get(TAG_JOB) == spec.job_id and r.tags.get(TAG_OWNER) == owner
                  and r.tags.get(TAG_IDEMPOTENCY) == ctx.idempotency_key,
                  "resource missing it-job-id / it-owner / it-idem tags")
    owned = adapter.list_owned_resources(owner)
    rep.check("list_owned.finds_by_idempotency", bool(find_by_idempotency(owned, ctx.idempotency_key)))
    obs = adapter.observe(ctx, receipt.resources)
    rep.check("observe.status_enum", isinstance(obs.status, ProviderStatus))
    rep.check("teardown.succeeds", adapter.teardown(receipt.resources))
    rep.check("teardown.idempotent", adapter.teardown(receipt.resources))
    gone = adapter.observe(ctx, receipt.resources)
    rep.check("observe.after_teardown_not_found", gone.status is ProviderStatus.NOT_FOUND,
              f"got {gone.status.value}")
    rep.check("list_owned.empty_after_teardown",
              not find_by_idempotency(adapter.list_owned_resources(owner), ctx.idempotency_key))
    return rep
