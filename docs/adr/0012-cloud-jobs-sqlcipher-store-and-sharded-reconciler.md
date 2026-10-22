# ADR-0012: Cloud Jobs Dedicated SQLCipher Store (`cloud_jobs.db`), Sharded `JobSpec`, and Pure Reconciler

- **Status:** Accepted (Locked 2026-10-19, Store Correction 2026-10-19)
- **Tracking:** [#824](https://github.com/ACFHarbinger/Image-Toolkit/issues/824), [#826](https://github.com/ACFHarbinger/Image-Toolkit/issues/826), [#827](https://github.com/ACFHarbinger/Image-Toolkit/issues/827), [#828](https://github.com/ACFHarbinger/Image-Toolkit/issues/828), [#829](https://github.com/ACFHarbinger/Image-Toolkit/issues/829)

## Context

The Cloud Jobs Service (`middleware/src/cloud/`) offloads CPU-heavy and GPU-heavy workloads across 8 cloud providers (AWS, GCP, Azure, Cloudflare, Oracle, RunPod, Hyperstack, Thunder Compute). Early proposals referenced PostgreSQL due to a stale `AGENTS.md` note, even though Image-Toolkit migrated its unified library to encrypted SQLCipher (`~/.image-toolkit/library.db`) on 2026-07-27.

## Decision

1. **Dedicated encrypted SQLCipher store (`~/.image-toolkit/cloud_jobs.db`, #827):**
   - Cloud Jobs uses its own encrypted SQLCipher database (`cloud_jobs.db`) via `backend.database.Database`, keyed by its own secret delivered to the daemon as a C++ sealed lease (ADR-0005).
   - No external database server is required, and cross-machine leader/observer election is dropped (jobs stay on the submitting machine).
   - `cloud_jobs.db` stores jobs, attempts, shards, an append-only `job_events` table, risk rules, and an **unpruned spend ledger** (while job rows/events/logs prune after N days with optional export).
   - When `cloud_jobs.db` cannot be opened (e.g., expired lease or file lock), new submissions are blocked while the daemon's JSONL Write-Ahead Log (WAL) continues teardown obligations and reconciliation, syncing back once the store reopens.
2. **Provider-neutral sharded `JobSpec` and 5-method adapter contract (#826):**
   - Both origin-tab submissions and the Cloud Compute Request Builder construct the same `JobSpec` (a manifest of shards: file slices for extraction, prompt slices with fixed seeds for ComfyUI, image-ID ranges for indexing, single shard for LoRA).
   - Every provider adapter implements five methods (`plan`, `submit`, `observe`, `teardown`, `collect(attempt, shard)`) plus an SDK-free capability manifest, graded by an adapter certification kit (`declared`, `recorded`, `live-smoke`).
3. **Deterministic state machine and pure reconciler (#828):**
   - Jobs progress through `queued → submitting → provisioning → running → collecting → settling → terminal` (with clock-triggered transitions for scheduled `queued` jobs).
   - Before any provider call, intent and an idempotency key are persisted; unknown submit outcomes reconcile by listing tagged provider resources before retrying.
   - The reconciler is a pure function `(state, observation, settings) → actions` for deterministic crash replay.

## Consequences

- Cloud Jobs operates with zero external DB infrastructure while preserving crash-safe teardown and lifetime spend tracking.
- Embedding/phash index outputs import into `library.db`'s `embeddings` table after staging and hash verification.
