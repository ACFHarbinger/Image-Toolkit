// SidecarTransport: ndjson JSON-RPC over an injected stdio channel
// (W0-12, #876; Codex R1/R6).
//
// The channel is the seam the Tauri Rust shell binds to the sidecar
// child's stdin/stdout later — here it is just `{send(line), onLine(cb)}`
// so tests can drive a loopback. Attach performs the `system.handshake`
// version negotiation (the UI and sidecar ship as one tested pair); every
// later request waits on that attach. In-flight requests are tracked by id
// and resolve/reject as response frames arrive; event frames (`channel`
// key) are forwarded to `onEvent`.

import { HostClientError } from "./errors";
import type { Transport } from "./transport";
import {
  BRIDGE_PROTOCOL_NAME,
  BRIDGE_PROTOCOL_VERSION,
  isEventFrame,
  isResponseFrame,
  type BridgeEvent,
  type HandshakeResult,
  type ResponseFrame,
} from "./types";

export interface StdioChannel {
  send(line: string): void;
  onLine(cb: (line: string) => void): void;
}

export interface SidecarTransportOptions {
  clientName?: string;
  clientVersion?: string;
  onEvent?: (event: BridgeEvent) => void;
  onProtocolError?: (error: HostClientError) => void;
}

function parseVersion(version: string): [number, number, number] {
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(version);
  if (!match) throw HostClientError.local("bridge.version_mismatch", { client: version });
  return [Number(match[1]), Number(match[2] ?? 0), Number(match[3] ?? 0)];
}

function inRange(version: string, min: string, max: string): boolean {
  const v = parseVersion(version);
  const lo = parseVersion(min);
  const hi = parseVersion(max);
  for (let i = 0; i < 3; i += 1) {
    if (v[i] !== lo[i]) return v[i] > lo[i];
  }
  for (let i = 0; i < 3; i += 1) {
    if (v[i] !== hi[i]) return v[i] < hi[i];
  }
  return true;
}

export class SidecarTransport implements Transport {
  private nextId = 0;
  private readonly inflight = new Map<
    string,
    { resolve: (result: unknown) => void; reject: (error: HostClientError) => void }
  >();
  private attachPromise: Promise<HandshakeResult> | null = null;

  constructor(
    private readonly channel: StdioChannel,
    private readonly options: SidecarTransportOptions = {},
  ) {
    channel.onLine((line) => this.handleLine(line));
  }

  /** Handshake-on-attach, memoized: resolves with the negotiated result. */
  attach(): Promise<HandshakeResult> {
    this.attachPromise ??= this.call("system.handshake", {
      protocol: BRIDGE_PROTOCOL_NAME,
      client: {
        name: this.options.clientName ?? "image-toolkit-webview",
        version: this.options.clientVersion ?? BRIDGE_PROTOCOL_VERSION,
      },
    }).then((result) => this.acceptHandshake(result as HandshakeResult));
    return this.attachPromise;
  }

  async request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    if (method !== "system.handshake") await this.attach();
    return this.call(method, params);
  }

  close(): void {
    const error = new HostClientError({
      code: "bridge.down",
      retryable: true,
      message_key: "bridge.unavailable",
    });
    for (const pending of this.inflight.values()) pending.reject(error);
    this.inflight.clear();
  }

  private call(method: string, params: Record<string, unknown>): Promise<unknown> {
    const id = `req-${(this.nextId += 1)}`;
    return new Promise((resolve, reject) => {
      this.inflight.set(id, { resolve, reject });
      this.channel.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    });
  }

  private acceptHandshake(result: HandshakeResult): HandshakeResult {
    if (result.protocol !== BRIDGE_PROTOCOL_NAME) {
      throw new HostClientError({
        code: "bridge.protocol_mismatch",
        retryable: false,
        message_key: "bridge.errors.protocol_mismatch",
        details: { expected: BRIDGE_PROTOCOL_NAME, got: result.protocol },
      });
    }
    const clientVersion = this.options.clientVersion ?? BRIDGE_PROTOCOL_VERSION;
    const { min, max } = result.compatibility;
    if (!inRange(clientVersion, min, max)) {
      throw new HostClientError({
        code: "bridge.version_mismatch",
        retryable: false,
        message_key: "bridge.errors.version_mismatch",
        details: { client: clientVersion, min, max },
      });
    }
    return result;
  }

  private handleLine(line: string): void {
    let frame: Record<string, unknown>;
    try {
      frame = JSON.parse(line);
    } catch {
      // stdout purity is the sidecar's contract; a non-JSON line is fatal
      // for the pending exchange it might have belonged to.
      const error = new HostClientError({
        code: "bridge.parse_error",
        retryable: false,
        message_key: "bridge.errors.parse_error",
        details: { reason: "line is not JSON" },
      });
      this.options.onProtocolError?.(error);
      return;
    }
    if (isEventFrame(frame)) {
      this.options.onEvent?.(frame as unknown as BridgeEvent);
      return;
    }
    if (isResponseFrame(frame)) {
      this.settle(frame as unknown as ResponseFrame);
    }
  }

  private settle(frame: ResponseFrame): void {
    const pending = this.inflight.get(String(frame.id));
    if (!pending) return; // late/unknown id: drop
    this.inflight.delete(String(frame.id));
    if (frame.error) pending.reject(new HostClientError(frame.error.data));
    else pending.resolve(frame.result ?? null);
  }
}
