import type { BridgeRequest, BridgeResponse } from "../../../contracts/generated/ts";
import { bridgeUnavailable, BridgeTransportError } from "./errors";
import type { BridgeTransport } from "./transport";

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface DjangoTransportOptions {
  readonly baseUrl: string;
  readonly fetchImpl?: FetchLike;
}

/** Django/remote adapter: one bridge request per HTTP POST, no extra envelope. */
export class DjangoTransport implements BridgeTransport {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;

  constructor(options: DjangoTransportOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
  }

  async request(request: BridgeRequest): Promise<BridgeResponse> {
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}/bridge/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
    } catch (error) {
      throw bridgeUnavailable({ reason: error instanceof Error ? error.name : "fetch failed" });
    }
    if (!response.ok) {
      throw bridgeUnavailable({ status: response.status });
    }
    try {
      return (await response.json()) as BridgeResponse;
    } catch {
      throw new BridgeTransportError("Django bridge returned non-JSON");
    }
  }
}
