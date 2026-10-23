import { invoke as tauriInvoke } from "@tauri-apps/api/core";

import type { BridgeRequest, BridgeResponse } from "../../../contracts/generated/ts";
import type { BridgeTransport } from "./transport";

export type InvokeLike = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export interface RustTransportOptions {
  readonly invokeImpl?: InvokeLike;
  readonly command?: string;
}

/** Native adapter for commands that remain Rust-owned (dialogs, tray, OS). */
export class RustTransport implements BridgeTransport {
  private readonly invokeImpl: InvokeLike;
  private readonly command: string;

  constructor(options: RustTransportOptions = {}) {
    this.invokeImpl = options.invokeImpl ?? ((command, args) => tauriInvoke(command, args));
    this.command = options.command ?? "bridge_request";
  }

  request(request: BridgeRequest): Promise<BridgeResponse> {
    return this.invokeImpl<BridgeResponse>(this.command, { request });
  }
}
