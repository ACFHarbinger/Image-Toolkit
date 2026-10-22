// HostClient: the single frontend entry point over the transport adapters
// (W0-12, #876; OpenCode §4).
//
// Frontend code calls `hostClient.<operation>()` exclusively; the manifest
// decides which transport serves the operation. One thin typed method per
// contract operation — payload types come from `contracts/generated/ts`.

import { HostClientError } from "./errors";
import { OPERATION_MANIFEST, type OperationRow, type TransportKind } from "./manifest";
import type { Transport } from "./transport";
import type {
  CancelResult,
  JobState,
  JobStatus,
  ListResult,
  PingResult,
  SubmitResult,
} from "../../../contracts/generated/ts";

export type Transports = Partial<Record<TransportKind, Transport>>;

export class HostClient {
  constructor(
    private readonly transports: Transports,
    private readonly manifest: readonly OperationRow[] = OPERATION_MANIFEST,
  ) {}

  /** Liveness probe (session-owned). */
  ping(): Promise<PingResult> {
    return this.call<PingResult>("ping");
  }

  /** Submit a durable job; `spec` is opaque at the bridge layer. */
  submitJob(kind: string, spec: Record<string, unknown>): Promise<SubmitResult> {
    return this.call("submitJob", { kind, spec });
  }

  /** Idempotent cancel: safe to retry, safe on a terminal job. */
  cancelJob(jobId: string): Promise<CancelResult> {
    return this.call("cancelJob", { job_id: jobId });
  }

  jobStatus(jobId: string): Promise<JobStatus> {
    return this.call("jobStatus", { job_id: jobId });
  }

  listJobs(filter?: { states?: JobState[]; limit?: number }): Promise<ListResult> {
    return this.call("listJobs", { ...filter });
  }

  /** Native file-open dialog (Rust shell). */
  pickFiles(options?: Record<string, unknown>): Promise<unknown> {
    return this.call("pickFiles", options);
  }

  /** Native OS notification (Rust shell). */
  notify(title: string, body: string): Promise<unknown> {
    return this.call("notify", { title, body });
  }

  isCancelable(operation: string): boolean {
    return this.row(operation).cancelable;
  }

  transportFor(operation: string): TransportKind {
    return this.row(operation).transport;
  }

  private row(operation: string): OperationRow {
    const row = this.manifest.find((entry) => entry.operation === operation);
    if (!row) {
      throw HostClientError.local("hostclient.unknown_operation", { operation });
    }
    return row;
  }

  private async call<T>(operation: string, params?: Record<string, unknown>): Promise<T> {
    const row = this.row(operation);
    const transport = this.transports[row.transport];
    if (!transport) {
      throw HostClientError.local("hostclient.no_transport", {
        operation,
        transport: row.transport,
      });
    }
    return (await transport.request(row.method, params ?? {})) as T;
  }
}
