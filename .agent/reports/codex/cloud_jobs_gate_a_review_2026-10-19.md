# Cloud Jobs Gate A review

— Codex, 2026-10-19. Reviewed Claude's `9d601ac1f..c926f89b3` implementation and current bus decisions. Uses the newly confirmed SQLCipher cloud store; earlier PostgreSQL proposals are superseded.

## Verdict

Core lifecycle fixes below are implemented and verified. Do not treat this as approval for paid adapters: the remaining integration gaps below need resolution before execution can enforce the full agreed policy. No live calls, benchmark or directory-wide suite ran.

## Fixed

- **High — crash after teardown could strand a successful job in `collecting`.** Persist outcome/settling and its cleanup obligation before destructive IO. Atomically record attempt completion and its ledger row.
- **High — retries/fallbacks could provision while the previous attempt still billed.** Persist restart intent in the existing event log, wait for confirmed teardown, then atomically create the replacement attempt and consume the intent. This also preserves the chosen fallback through restart.
- **High — settling resources disappeared from admission accounting.** Keep cleanup obligations in concurrency/reservation accounting; release reservations only at the terminal transition. Queued cancellation now releases its reservation too.
- **High — observed spend existed only in engine memory.** Persist the highest observed attempt cost; a restart or subsequent `NOT_FOUND` observation cannot erase it.
- **High — Settings defaults were not enforced by the running engine.** Apply default job spend/runtime caps and respect `hard_caps_enabled`.
- **High — unexpected submit exceptions were treated as proof nothing was provisioned.** Reconcile unknown outcomes. Adapters must now use `SubmitRejected` only for a definitive rejection; quota/out-of-stock inherit that contract. The fake follows it.
- **High — quota/submit rejection was lost between ticks after a crash.** Persist rejection and attempt completion atomically; recover the rejection for that attempt rather than starting another one.
- **High — Force stop failed when observation failed.** It now reaches teardown without requiring the provider status endpoint.
- **High — an invalid secret decision bypassed preflight's explicit keep/strip choice.** Unknown decision values block upload.
- **Medium — incomplete estimates were labeled known.** Missing required egress/storage pricing or runtime now marks the estimate incomplete while retaining the available breakdown.

## Remaining findings before paid execution

1. **High — no authoritative preflight/admission boundary yet.** `JobEngine.submit()` accepts raw `JobSpec`, an unchecked override flag and an optional zero reservation. It does not call `run_preflight`; scheduled starts and automatic fallback do not recheck capability/privacy/quota/cost policy. These are separate callable pieces today, not an enforced submission path. Gate B's authenticated command path must bind the accepted sanitized spec, acknowledgements and cost reservation to execution, and revalidate scheduled/fallback placement. This needs a shared orchestration contract rather than a GUI-only fix.
2. **High — monthly caps are only a preflight calculation.** `run_preflight()` takes a caller-provided month-to-date value, defaulting to zero. EngineSettings/admission do not carry the monthly cap, and the check omits concurrent commitments. Two independently accepted jobs can exceed the month's remaining budget. Add serialized ledger-backed reservation/admission and running-budget enforcement; billing-API reconciliation can remain adapter-specific.
3. **High — graceful cancellation/cap cleanup can still depend on successful checkpoint/collection.** `_apply()` executes those operations before settlement. Exceptions prevent teardown; an unverified collect returns false but later actions may still tear down. The collection contract needs to distinguish durable remote artifacts from ephemeral instance outputs and retain a recoverable collection obligation. Test unavailable checkpoint/download endpoints and invalid checksums before enabling paid jobs. Force stop now provides a teardown path, but does not settle this graceful-stop/output-retention contract.

These are explicit remaining findings, not claims that the daemon integration is already present. No public API redesign or schema migration was introduced in this review patch.

## Validation

54 focused tests passed, run one file at a time:

- `test_cloud_jobs_recovery_review.py`: 10.
- `test_cloud_jobs_engine.py`: 21.
- `test_cloud_jobs_crash_matrix.py`: 4.
- `test_cloud_jobs_preflight.py`: 8.
- `test_cloud_jobs_risk_cost.py`: 11.

The first five new lifecycle regressions and three later failure-path regressions failed before their fixes. The invalid-secret-choice regression also failed before its fix. Ruff and `git diff --check` pass. Tests used the real encrypted store and fake providers, with `--confcutdir=backend/test/cloud`, no pytest cache, and isolated basetemps under `~/Downloads/Data/Tests/cloud-gate-a-*`; broad backend fixtures were excluded. The full Cloud Jobs directory suite was not run.
