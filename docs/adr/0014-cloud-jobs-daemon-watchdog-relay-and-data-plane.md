# ADR-0014: Cloud Jobs Local Daemon, Cloud Watchdog/Relay, Content-Addressed Data Plane, and Digest-Pinned Workers

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#833](https://github.com/ACFHarbinger/Image-Toolkit/issues/833), [#834](https://github.com/ACFHarbinger/Image-Toolkit/issues/834), [#836](https://github.com/ACFHarbinger/Image-Toolkit/issues/836), [#840](https://github.com/ACFHarbinger/Image-Toolkit/issues/840), [#847](https://github.com/ACFHarbinger/Image-Toolkit/issues/847)

## Context

Cloud jobs require reliable background polling, dead-man teardown when the desktop is powered off, outbound-only remote control from mobile/web clients without opening inbound firewall ports, deduplicated staging across object buckets and Cloud Sync remotes, and reproducible headless worker environments.

## Decision

1. **Single-instance local daemon (#834):** Runs as a sibling process under the supervisor (Linux first in v1) with authenticated local IPC, protocol version handshake, C++ sealed store lease, and JSONL WAL recovery.
2. **Single-deployable cloud Watchdog + Relay (#836):**
   - Deployed to the user's GCP account (Cloud Function / Cloud Run) by default, with Cloudflare Worker as an alternative.
   - Exposes a **teardown endpoint** (enforces heartbeat deadlines when the desktop is offline) and a **command endpoint** (outbound-pulled by the daemon over TLS with scoped tokens and audit logs; remote retries stay within existing job leases).
3. **Unified content-addressed data plane (#833):**
   - Supports object buckets (S3, GCS, Azure Blob, R2 via presigned URLs), provider-native volumes, and Cloud Sync remotes (Dropbox/OneDrive temporary links or transit buckets for Google Drive).
   - Inputs are content-addressed by `sha256`; model caches use reference-counted per-region volumes; workers stream `events.jsonl` telemetry via presigned URLs polled by byte range every 2–5s.
   - Outputs land in a quarantined `Cloud Jobs/<job-id>` collection until verified; library embeddings/phashes auto-import into `library.db` only when source hashes and schema versions match.
4. **Digest-pinned headless workers and instance packing (#840):**
   - First-party CPU and CUDA Dockerfiles publish to a user-owned registry and boot headlessly (no web UI, no floating IP, no forwarded ports).
   - Supports `1:1` (default), sequential chaining, and parallel instance packing.
   - Cloud Jobs Gate D (#847–#852) ships as the first Tauri-only feature (`cloud.jobs` panel and pop-out window).

## Consequences

- Zero inbound ports are opened on either the desktop workstation or cloud worker instances.
- Offline workstations remain protected against runaway cloud instances via the user-owned watchdog.
