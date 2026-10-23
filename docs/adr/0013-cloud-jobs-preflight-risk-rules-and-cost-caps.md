# ADR-0013: Cloud Jobs Preflight Pipeline, Editable Risk Rules, Cost Calibration, and Leak Protection

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#830](https://github.com/ACFHarbinger/Image-Toolkit/issues/830), [#831](https://github.com/ACFHarbinger/Image-Toolkit/issues/831), [#832](https://github.com/ACFHarbinger/Image-Toolkit/issues/832), [#837](https://github.com/ACFHarbinger/Image-Toolkit/issues/837), [#838](https://github.com/ACFHarbinger/Image-Toolkit/issues/838)

## Context

Dispatching GPU workloads across third-party cloud providers carries financial and data-exposure risks: accidental credential leaks in ComfyUI graphs, unapproved uploads of sensitive datasets, runaway instance spend, and orphaned cloud VMs if a local machine loses connectivity.

## Decision

1. **8-stage pure preflight pipeline (#831):** Both UI preview and backend submission execute the exact same pure pipeline in fixed order:
   1. Schema/spec validation
   2. Data-class allowlist check (`public` / `private` / `sensitive`)
   3. ComfyUI widget secret scan (blocks submit until stripped or explicitly kept; logs keep redacted graphs)
   4. Weight cloud-class check (`allow` / `warn` / `block`; `block` weights never enter staging manifests)
   5. Provider quota/capacity probe
   6. Deterministic total-job cost estimation
   7. Risk rule evaluation
   8. Explicit **Plan & cost confirmation sheet** click
2. **Editable risk and capability rules (#830):**
   - Seeded from YAML into `cloud_jobs.db` and editable in Settings (`block`, `warn`, `info`).
   - Capability rules (e.g., Cloud Run GPU timeout limits) are also editable per Harbinger's decision: overriding a capability rule attaches a **permanent ⚠** to affected jobs, and any subsequent provider failure is treated as **structural** (consuming zero retry budget and preventing automatic fallback).
3. **Cost catalogue, caps, and calibration (#832):**
   - Ranks candidates by estimated **total job cost** (startup + compute + egress + retained storage + expected retries, respecting billing granularity and deadlines) and snapshots catalogue rows per job.
   - Enforces per-job runtime/spend caps, monthly caps, and admission caps; reaching a hard cap triggers forward prediction, shard checkpointing, cancellation, and teardown while preserving partial outputs.
4. **Multi-layer leak protection and emergency stop (#837, #838):**
   - Every cloud resource carries `it-job-id`, `it-owner`, and `it-expires-at` tags, backed by startup/on-demand orphan sweeps (which surface in the Resources view and never kill silently), in-instance dead-man switches, provider-native deadlines, and the cloud watchdog.
   - Supports three stop levels: **Cancel** (checkpoint + collect + teardown), **Force stop** (skip checkpoint), and **"Stop all cloud activity"** (global emergency stop that checkpoint-cancels all jobs, revokes leases, triggers watchdog teardown, and blocks new submits).

## Consequences

- No cloud resource can be provisioned without passing secret scanning, quota verification, cost cap checks, and leak-tag attachment.
- Workers never receive vault keys, database credentials, Cloud Sync OAuth tokens, or Hugging Face tokens.
