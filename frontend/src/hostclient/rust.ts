// RustTransport: native-only operations through an injected Tauri `invoke`
// (W0-12, #876).
//
// Scope rule (roadmap §1): dialogs, tray, notifications and OS integration
// only — no business methods. A Rust command that duplicates a sidecar
// service is retired by moving its manifest row to `sidecar`, never by
// adding rows here.

import type { Transport } from "./transport";

export type InvokeFn = (command: string, args?: Record<string, unknown>) => Promise<unknown>;

export class RustTransport implements Transport {
  constructor(private readonly invokeFn: InvokeFn) {}

  /** `method` is the Tauri command name for native ops (see manifest). */
  request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    return this.invokeFn(method, params);
  }

  close(): void {
    // The Rust shell owns its own lifetime.
  }
}
