import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import { invoke as tauriInvoke } from "@tauri-apps/api/core";

import type { BridgeEvent, BridgeRequest, BridgeResponse } from "../../../contracts/generated/ts";
import type { BridgeTransport } from "./transport";

export type InvokeLike = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export type ListenLike = (event: string, listener: (event: { payload: BridgeEvent }) => void) => Promise<UnlistenFn>;

export interface RustTransportOptions {
  readonly listenImpl?: ListenLike;
  readonly invokeImpl?: InvokeLike;
  readonly command?: string;
}

/** Native adapter for commands that remain Rust-owned (dialogs, tray, OS). */
export class RustTransport implements BridgeTransport {
  private readonly invokeImpl: InvokeLike;
  private readonly command: string;
  private readonly listenImpl: ListenLike;
  private readonly listeners = new Set<(frame: BridgeEvent) => void>();
  private subscription?: Promise<UnlistenFn>;
  private closed = false;

  constructor(options: RustTransportOptions = {}) {
    this.invokeImpl = options.invokeImpl ?? ((command, args) => tauriInvoke(command, args));
    this.listenImpl = options.listenImpl ?? ((event, listener) => listen<BridgeEvent>(event, listener));
    this.command = options.command ?? "bridge_request";
  }

  async request(request: BridgeRequest): Promise<BridgeResponse> {
    if (this.closed) throw new Error("Rust transport is closed");
    // Event registration must finish before a job can emit its first frame.
    if (this.subscription) await this.subscription;
    if (this.closed) throw new Error("Rust transport is closed");
    return this.invokeImpl<BridgeResponse>(this.command, { request });
  }

  onEvent(listener: (frame: BridgeEvent) => void): () => void {
    if (this.closed) throw new Error("Rust transport is closed");
    this.listeners.add(listener);
    this.subscription ??= this.listenImpl("bridge-event", ({ payload }) => {
      if (!this.closed) for (const callback of this.listeners) callback(payload);
    });
    // request() observes registration failures; avoid an unhandled rejection
    // when a subscriber is mounted before any command is sent.
    void this.subscription.catch(() => {});
    return () => { this.listeners.delete(listener); };
  }

  async close(): Promise<void> {
    this.closed = true;
    this.listeners.clear();
    if (this.subscription) {
      const subscription = this.subscription;
      this.subscription = undefined;
      const unlisten = await subscription;
      unlisten();
    }
  }

}
