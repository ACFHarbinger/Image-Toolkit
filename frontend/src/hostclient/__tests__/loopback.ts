// Loopback channel pair + a minimal contract-valid responder replaying the
// reference sidecar semantics (handshake gate, ping, in-memory jobs,
// idempotent cancel). Mirrors `middleware/src/sidecar/` — kept in sync via
// the shared conformance fixtures, not by diverging here.

import type { StdioChannel } from "../sidecar";

export function loopbackPair(): { client: StdioChannel; server: StdioChannel } {
  const clientCbs: Array<(line: string) => void> = [];
  const serverCbs: Array<(line: string) => void> = [];
  return {
    client: {
      send: (line) => serverCbs.forEach((cb) => cb(line)),
      onLine: (cb) => clientCbs.push(cb),
    },
    server: {
      send: (line) => clientCbs.forEach((cb) => cb(line)),
      onLine: (cb) => serverCbs.push(cb),
    },
  };
}

const RPC_CODES: Record<string, number> = {
  "bridge.parse_error": -32700,
  "bridge.invalid_request": -32600,
  "bridge.method_not_found": -32601,
  "bridge.invalid_params": -32602,
};

interface ErrorSpec {
  code: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
}

export interface FakeSidecarOptions {
  minVersion?: string;
  maxVersion?: string;
  handshakeGate?: boolean;
}

export class FakeSidecar {
  private ready = false;
  private seq = 0;
  private nextJob = 0;
  private readonly jobs = new Map<string, { kind: string; state: string }>();

  constructor(
    private readonly channel: StdioChannel,
    private readonly options: FakeSidecarOptions = {},
  ) {
    channel.onLine((line) => this.handle(line));
  }

  private handle(line: string): void {
    const frame = JSON.parse(line);
    const id = frame.id;
    const method = frame.method as string;
    const params = (frame.params ?? {}) as Record<string, unknown>;
    if (this.options.handshakeGate !== false && !this.ready && method !== "system.handshake") {
      return this.fail(id, { code: "bridge.invalid_request", details: { reason: "handshake_required" } });
    }
    switch (method) {
      case "system.handshake":
        return this.handshake(id, params);
      case "system.ping":
        return this.respond(id, { ok: true });
      case "jobs.submit":
        return this.submit(id, params);
      case "jobs.cancel":
        return this.cancel(id, params);
      case "jobs.status":
        return this.status(id, params);
      case "jobs.list":
        return this.list(id, params);
      default:
        return this.fail(id, { code: "bridge.method_not_found", details: { method } });
    }
  }

  private handshake(id: string, params: Record<string, unknown>): void {
    if (params.protocol !== "image-toolkit-bridge") {
      return this.fail(id, { code: "bridge.protocol_mismatch" });
    }
    const client = (params.client as { version: string }).version;
    const min = this.options.minVersion ?? "1.0.0";
    const max = this.options.maxVersion ?? "1.0.0";
    if (client < min || client > max) {
      return this.fail(id, {
        code: "bridge.version_mismatch",
        details: { client, min, max },
      });
    }
    this.ready = true;
    this.respond(id, {
      protocol: "image-toolkit-bridge",
      version: "1.0.0",
      compatibility: { min, max },
      capabilities: ["system", "jobs"],
    });
  }

  private submit(id: string, params: Record<string, unknown>): void {
    const jobId = `job-fake-${(this.nextJob += 1)}`;
    this.jobs.set(jobId, { kind: params.kind as string, state: "queued" });
    this.event(jobId, "queued");
    this.respond(id, { job_id: jobId });
  }

  private cancel(id: string, params: Record<string, unknown>): void {
    const jobId = params.job_id as string;
    const job = this.jobs.get(jobId);
    if (!job) return this.fail(id, { code: "jobs.not_found", details: { job_id: jobId } });
    if (job.state !== "cancelled") {
      job.state = "cancelled";
      this.event(jobId, "cancelled");
    }
    this.respond(id, { ok: true });
  }

  private status(id: string, params: Record<string, unknown>): void {
    const jobId = params.job_id as string;
    const job = this.jobs.get(jobId);
    if (!job) return this.fail(id, { code: "jobs.not_found", details: { job_id: jobId } });
    this.respond(id, { job_id: jobId, kind: job.kind, state: job.state });
  }

  private list(id: string, params: Record<string, unknown>): void {
    const states = (params.states as string[] | undefined) ?? [];
    const jobs = [...this.jobs.entries()]
      .filter(([, job]) => states.length === 0 || states.includes(job.state))
      .map(([jobId, job]) => ({ job_id: jobId, kind: job.kind, state: job.state }));
    this.respond(id, { jobs });
  }

  private event(jobId: string, state: string): void {
    this.seq += 1;
    this.channel.send(
      JSON.stringify({
        channel: "jobs",
        seq: this.seq,
        kind: "fact",
        durable: true,
        ts: new Date().toISOString(),
        payload: { job_id: jobId, state },
      }),
    );
  }

  private respond(id: string, result: unknown): void {
    this.channel.send(JSON.stringify({ jsonrpc: "2.0", id, result }));
  }

  private fail(id: string, spec: ErrorSpec): void {
    const messageKey = `bridge.errors.${spec.code.split(".").pop()}`;
    this.channel.send(
      JSON.stringify({
        jsonrpc: "2.0",
        id,
        error: {
          code: RPC_CODES[spec.code] ?? -32000,
          message: messageKey,
          data: {
            code: spec.code,
            retryable: spec.retryable ?? false,
            message_key: messageKey,
            ...(spec.details ? { details: spec.details } : {}),
          },
        },
      }),
    );
  }
}
