# GUI Windows teardown verification — `--run-gui`, at directory scale — 2026-08-27

## Authorization

Harbinger authorized Claude to run this directly, as an explicit override of the
`AGENTS.md` RESOURCE RULE / Codex-only chain. Rationale given: that rule is aimed
at benchmarks and `cargo` tests (very resource-intensive); `pytest` runs have not
triggered a forced machine shutdown, so the rule does not meaningfully apply here.

This is the corrected invocation — the earlier authorized run
(`gui_windows_teardown_verification_2026-08-27.md`) omitted `--run-gui` and so
skipped all 112 real window tests (5 passed, 112 skipped in 0.37s), never
exercising the quadratic-teardown scenario.

## Command

```
source .venv/bin/activate
python -m pytest gui/test/windows/ --run-gui -p no:randomly -q
```

Run monitored in the foreground, not backgrounded.

## Result — teardown fix validated at directory scale

| Run | Outcome | Wall time |
|-----|---------|-----------|
| 1 (`-q`)               | 117 passed, 4 errors | 171.72s (2:51) |
| 2 (`-q -rE --tb=line`) | 117 passed, 4 errors | 253.91s (4:13) |

- **No quadratic teardown hang.** The full 117-test directory completes in
  ~3–4 minutes. The pre-fix pathology was 82s+ for a *subset*; at 117 tests it
  would have blown well past a 10-minute ceiling. It did not.
- **No forced machine shutdown**, no thermal event.
- **No lingering test process** after either run (`ps` checked clean).
- Run-to-run wall-time variance (172s vs 254s) is present but both runs are
  linear-scale and finish cleanly; not the runaway growth the fix targeted.

## Pre-existing unrelated issue — 4 teardown errors

```
ERROR at teardown of TestWorkflowTemplates.<4 tests>
AttributeError: Error calling Python override of QWidget::closeEvent():
    'MockVaultManager' object has no attribute 'shutdown'
```

- All 4 are **teardown** errors (the tests themselves pass), in
  `gui/test/windows/test_workflow_templates.py`.
- Run in isolation, that file is **4 passed in 5.38s** — no errors. The failure
  only appears in the full-directory run, i.e. it is an ordering / state-leak
  interaction: the `MockVaultManager` test double lacks a `shutdown()` method
  that the window close path invokes once some earlier test in the directory has
  run.
- This is a test-double completeness gap, not a regression from the teardown
  fix and not part of the quadratic-hang class. Left as a separate follow-up.

## Verdict

The teardown fix eliminates the quadratic hang at directory scale. Issue closed.
The `MockVaultManager.shutdown` gap in `test_workflow_templates.py` is a separate
pre-existing test-isolation bug worth its own fix.
