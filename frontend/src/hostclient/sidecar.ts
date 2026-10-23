import type { BridgeEvent, BridgeRequest, BridgeResponse } from "../../../contracts/generated/ts";
import { BridgeTransportError } from "./errors";
import type { BridgeTransport } from "./transport";

/**
 * Framed stdio boundary owned by the native shell. Implementations feed one
 * JSON object per line; this class only correlates protocol frames.
 */
export interface SidecarConnection {
  sendLine(line: string): void;
  onLine(listener: (line: string) => void): () => void;
  onClose?(listener: (reason?: unknown) => void): () => void;
  reconnect?(): Promise<void> | void;
  close?(): Promise<void> | void;
}

interface PendingRequest {
  resolve(response: BridgeResponse): void;
  reject(error: unknown): void;
}

export class SidecarTransport implements BridgeTransport {
  private readonly connection: SidecarConnection;
  private readonly pending = new Map<string | number, PendingRequest>();
  private readonly eventListeners = new Set<(frame: BridgeEvent) => void>();
  private readonly detachLine: () => void;
  private readonly detachClose?: () => void;
  /** A dropped connection. Cleared only after `reconnect()` resolves. */
  private closed = false;
  /** `close()` is terminal: listeners are gone, so reset must not reopen it. */
  private stopped = false;

  constructor(connection: SidecarConnection) {
    this.connection = connection;
    this.detachLine = connection.onLine((line) => this.handleLine(line));
    this.detachClose = connection.onClose?.((reason) => this.handleClose(reason));
  }

  request(request: BridgeRequest): Promise<BridgeResponse> {
    if (this.closed) {
      return Promise.reject(new BridgeTransportError("sidecar transport is closed"));
    }
    const id = request.id;
    if (id === null) {
      return Promise.reject(new BridgeTransportError("host requests require a non-null id"));
    }
    if (this.pending.has(id)) {
      return Promise.reject(new BridgeTransportError(`duplicate in-flight request id ${String(id)}`));
    }
    const response = new Promise<BridgeResponse>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
    try {
      this.connection.sendLine(`${JSON.stringify(request)}\n`);
    } catch (error) {
      this.pending.delete(id);
      return Promise.reject(error);
    }
    return response;
  }

  onEvent(listener: (frame: BridgeEvent) => void): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  async reset(): Promise<void> {
    if (this.stopped) {
      return;
    }
    await this.connection.reconnect?.();
    this.closed = false;
  }

  async close(): Promise<void> {
    if (this.stopped) {
      return;
    }
    this.stopped = true;
    this.closed = true;
    this.detachLine();
    this.detachClose?.();
    await this.connection.close?.();
    this.rejectPending(new BridgeTransportError("sidecar transport closed"));
  }

  private handleLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    let frame: unknown;
    try {
      frame = JSON.parse(trimmed);
    } catch {
      this.rejectPending(new BridgeTransportError("sidecar emitted a non-JSON frame"));
      return;
    }
    if (typeof frame !== "object" || frame === null || Array.isArray(frame)) {
      this.rejectPending(new BridgeTransportError("sidecar emitted a non-object frame"));
      return;
    }
    if ("jsonrpc" in frame) {
      const response = frame as BridgeResponse;
      const id = response.id;
      if (id === null) {
        return;
      }
      const pending = this.pending.get(id);
      if (!pending) {
        return;
      }
      this.pending.delete(id);
      pending.resolve(response);
      return;
    }
    for (const listener of this.eventListeners) {
      listener(frame as BridgeEvent);
    }
  }

  private handleClose(reason: unknown): void {
    this.closed = true;
    this.rejectPending(reason instanceof Error ? reason : new BridgeTransportError("sidecar closed"));
  }

  private rejectPending(error: unknown): void {
    const requests = [...this.pending.values()];
    this.pending.clear();
    for (const pending of requests) {
      pending.reject(error);
    }
  }
}
