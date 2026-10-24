import type {
  BridgeResponse,
  CancelResult,
  ConvertBatchParams,
  ConvertBatchResult,
  ConvertParams,
  ConvertResult,
  PrefillParams,
  PrefillResult,
  SummaryResult,
  HandshakeResult,
  JobStatus,
  ListParams,
  ListResult,
  PingResult,
  SubmitParams,
  SubmitResult,
} from "../../../contracts/generated/ts";
import { BridgeAppError, BridgeTransportError, decodeBridgeResult } from "./errors";
import { buildBridgeRequest, type BridgeTransport } from "./transport";

const PROTOCOL_NAME = "image-toolkit-bridge";

export interface HostClientOptions {
  readonly clientName: string;
  readonly clientVersion: string;
  /** Total attempts for retryable transport failures, including the first. */
  readonly reconnectAttempts?: number;
  readonly reconnectDelayMs?: number;
}

export class HostClient {
  private readonly transport: BridgeTransport;
  private readonly options: Required<HostClientOptions>;
  private ready: Promise<HandshakeResult> | undefined;
  private nextId = 1;

  constructor(transport: BridgeTransport, options: HostClientOptions) {
    this.transport = transport;
    this.options = {
      reconnectAttempts: 2,
      reconnectDelayMs: 25,
      ...options,
    };
  }

  connect(): Promise<HandshakeResult> {
    this.ready ??= this.send<HandshakeResult>("system.handshake", {
      protocol: PROTOCOL_NAME,
      client: { name: this.options.clientName, version: this.options.clientVersion },
    }).then((result) => {
      this.assertCompatible(result);
      return result;
    });
    this.ready.catch(() => {
      this.ready = undefined;
    });
    return this.ready;
  }

  async ping(): Promise<PingResult> {
    await this.connect();
    return this.send<PingResult>("system.ping", {});
  }

  async submitJob(params: SubmitParams): Promise<SubmitResult> {
    await this.connect();
    return this.send<SubmitResult>("jobs.submit", params as unknown as Record<string, unknown>);
  }

  async cancelJob(jobId: string): Promise<CancelResult> {
    await this.connect();
    return this.send<CancelResult>("jobs.cancel", { job_id: jobId });
  }

  async jobStatus(jobId: string): Promise<JobStatus> {
    await this.connect();
    return this.send<JobStatus>("jobs.status", { job_id: jobId });
  }

  async listJobs(params: ListParams = {}): Promise<ListResult> {
    await this.connect();
    return this.send<ListResult>("jobs.list", params as unknown as Record<string, unknown>);
  }

  async cloudJobsSummary(): Promise<SummaryResult> {
    await this.connect();
    return this.send<SummaryResult>("cloud_jobs.summary", {});
  }

  async cloudOfferPrefill(params: PrefillParams): Promise<PrefillResult> {
    await this.connect();
    return this.send<PrefillResult>("cloud_offer.prefill", params as unknown as Record<string, unknown>);
  }

  async convert(params: ConvertParams): Promise<ConvertResult> {
    await this.connect();
    return this.send<ConvertResult>("convert.convert", params as unknown as Record<string, unknown>);
  }

  async convertBatch(params: ConvertBatchParams): Promise<ConvertBatchResult> {
    await this.connect();
    return this.send<ConvertBatchResult>(
      "convert.convert_batch",
      params as unknown as Record<string, unknown>,
    );
  }

  onEvent(listener: Parameters<NonNullable<BridgeTransport["onEvent"]>>[0]): () => void {
    if (!this.transport.onEvent) {
      throw new BridgeTransportError("this transport has no event stream");
    }
    return this.transport.onEvent(listener);
  }

  async close(): Promise<void> {
    await this.transport.close?.();
    this.ready = undefined;
  }

  private async send<T>(method: string, params: Record<string, unknown>): Promise<T> {
    const attempts = Math.max(1, this.options.reconnectAttempts);
    let lastError: unknown;
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const request = buildBridgeRequest(method, this.allocateId(), params);
      try {
        const response: BridgeResponse = await this.transport.request(request);
        return decodeBridgeResult<T>(response, request.id);
      } catch (error) {
        lastError = error;
        const retryable =
          error instanceof BridgeTransportError ||
          (error instanceof BridgeAppError && error.retryable && method !== "jobs.submit");
        if (!retryable || attempt === attempts) {
          throw error;
        }
        await this.transport.reset?.();
        await delay(this.options.reconnectDelayMs * attempt);
      }
    }
    throw lastError;
  }

  private allocateId(): string {
    const id = `host-${this.nextId}`;
    this.nextId += 1;
    return id;
  }

  private assertCompatible(result: HandshakeResult): void {
    if (result.protocol !== PROTOCOL_NAME) {
      throw new BridgeAppError({
        code: "bridge.protocol_mismatch",
        retryable: false,
        message_key: "bridge.errors.protocol_mismatch",
        details: { expected: PROTOCOL_NAME, got: result.protocol },
      });
    }
    const { min, max } = result.compatibility;
    if (!versionInRange(this.options.clientVersion, min, max)) {
      throw new BridgeAppError({
        code: "bridge.version_mismatch",
        retryable: false,
        message_key: "bridge.errors.version_mismatch",
        details: { client: this.options.clientVersion, min, max },
      });
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseVersion(version: string): [number, number, number] {
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(version);
  if (!match) {
    throw new BridgeAppError({
      code: "bridge.version_mismatch",
      retryable: false,
      message_key: "bridge.errors.version_mismatch",
      details: { client: version },
    });
  }
  return [Number(match[1]), Number(match[2] ?? 0), Number(match[3] ?? 0)];
}

function compareVersion(left: string, right: string): number {
  const a = parseVersion(left);
  const b = parseVersion(right);
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) {
      return a[index] - b[index];
    }
  }
  return 0;
}

function versionInRange(version: string, minimum: string, maximum: string): boolean {
  return compareVersion(version, minimum) >= 0 && compareVersion(version, maximum) <= 0;
}
