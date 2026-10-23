# Targeted Tests for #879 Supervisor Binding Enforcement

**Date:** 2026-10-23

## Test additions (targeted only)

In `middleware/test/database/test_vault_sealed_leases.py` (class TestSealedStoreLeases):

```python
def test_enforce_binding_raises_on_missing(self):
    vm = VaultManager.create_guest_vault("test")
    with pytest.raises(ValueError, match="pid"):
        vm.handoff_daemon_lease(
            "store", "daemon", "/tmp",
            pid=0, ttl_seconds=3600, supervisor_session="sess",
            enforce_binding=True,
        )
    with pytest.raises(ValueError, match="ttl"):
        vm.handoff_daemon_lease(
            "store", "daemon", "/tmp",
            pid=123, ttl_seconds=0, supervisor_session="sess",
            enforce_binding=True,
        )
    with pytest.raises(ValueError, match="session"):
        vm.handoff_daemon_lease(
            "store", "daemon", "/tmp",
            pid=123, ttl_seconds=3600, supervisor_session="",
            enforce_binding=True,
        )
```

Existing tests already cover:
- PID match / mismatch on unseal (`test_pid_binding`, `test_genuine_separate_daemon_process`)
- TTL expiry (`test_ttl_expiration`)
- Session match / mismatch (`test_supervisor_session_binding`)
- 0600 key permissions and insecure rejection

For supervisor: assert `supervisor.supervisor_session` is a non-empty UUID after init; handoff is called for durable daemons (mock vault).

Run: `pytest middleware/test/database/test_vault_sealed_leases.py -k enforce_binding or pid or ttl or session --tb=short`

No full suite. RESOURCE RULE observed.
