# #879 targeted verification plan

Status: proposed coverage only; no new tests are implemented or reported passing by this branch.

Use the existing vault fixture and isolate data through `tmp_path` under `~/Downloads/Data/Tests/`. Do not create guest vaults in user directories. The current `handoff_daemon_lease` API has no `enforce_binding` argument; adapt tests to the production enforcement design when implemented.

Required cases:

- Reject zero/negative PID, zero/negative TTL and empty/whitespace session before minting; verify the native mint is not called.
- Supply the actual spawned PID and expected supervisor session; keep the child unready until private lease delivery succeeds.
- Fail closed and clean up a spawned child on mint/delivery failure; never expose lease material through logs, argv or heartbeats.
- Verify restart uses the replacement PID, renewal occurs before expiry, and reattached durable children follow the defined session transition.
- Preserve multi-store daemon key reuse; reject another daemon's key, insecure permissions and missing configured keys.
- Exercise genuine separate-process store access with matching bindings and reject wrong PID/session and expired leases.

Existing coverage includes `test_supervisor_session_binding` and `test_genuine_separate_daemon_process` in `middleware/test/database/test_vault_sealed_leases.py`; inspect assertions rather than treating their names as proof of production integration.

Example bounded command after the new tests exist, with a fresh basetemp:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest -q -o addopts='' \
  --confcutdir=middleware/test/database -p no:cacheprovider \
  --basetemp="$HOME/Downloads/Data/Tests/s879-binding-check" \
  middleware/test/database/test_vault_sealed_leases.py \
  -k 'enforce_binding or pid or ttl or session' --tb=short
```

Run any new supervisor cases as one selected fast test file. Full suites, GPU/corpus runs and benchmarks still require Codex coordination and Harbinger's explicit authorization per run. None is authorized or launched by this plan.
