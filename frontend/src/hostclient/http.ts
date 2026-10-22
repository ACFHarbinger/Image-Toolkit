// HttpTransport: the same contract methods over the Django `api/` surface
// (W0-12, #876) — for remote/mobile clients (Cloud Jobs G1), not the
// desktop webview.
//
// Expected endpoint shape (the Django bridge view lands in a later wave;
// this adapter defines the contract it must serve):
//   POST {baseUrl}/bridge/<method>        e.g. /api/bridge/jobs.submit
//   body: the method params as JSON
//   200 → the method result as JSON
//   non-200 → the wire error envelope {code, retryable, message_key,
//   details} as JSON (same shape the sidecar puts in error.data)
// `baseUrl` and `fetch` are injectable for tests.

import { HostClientError } from "./errors";
import type { Transport } from "./transport";
import type { BridgeError } from "./types";

export interface HttpTransportOptions {
  baseUrl: string;
  fetchFn?: typeof fetch;
}

export class HttpTransport implements Transport {
  private readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;

  constructor(options: HttpTransportOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchFn = options.fetchFn ?? fetch;
  }

  async request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const response = await this.fetchFn(`${this.baseUrl}/bridge/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    const body = (await response.json()) as unknown;
    if (!response.ok) {
      throw new HostClientError(body as BridgeError);
    }
    return body;
  }

  close(): void {
    // Stateless HTTP: nothing to release.
  }
}
