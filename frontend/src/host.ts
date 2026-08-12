/** Typed host seam shared by standalone Vite, Tauri, and Image-Toolkit tabs. */

import { invoke } from "@tauri-apps/api/core";

export interface HieHost {
  openMedia(): Promise<void>;
  exportDocument(): Promise<void>;
  notify(message: string): void;
}

interface IpcResponse {
  version: number;
  request_id: string;
  status: "ok" | "error";
  payload: Record<string, unknown>;
  error: string | null;
}

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `hie-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const browserHost: HieHost = {
  async openMedia(): Promise<void> {
    // A browser-safe fallback; Tauri/Image-Toolkit hosts replace this method.
  },
  async exportDocument(): Promise<void> {
    // A browser-safe fallback; Tauri/Image-Toolkit hosts replace this method.
  },
  notify(message: string): void {
    console.info(`[HIE] ${message}`);
  },
};

declare global {
  interface Window {
    __HIE_HOST__?: HieHost;
  }
}

export function getHieHost(): HieHost {
  if (window.__HIE_HOST__) return window.__HIE_HOST__;
  if ("__TAURI_INTERNALS__" in window) {
    const requireOk = async (command: string, args: Record<string, string>): Promise<void> => {
      const response = await invoke<IpcResponse>(command, args);
      if (response.status === "error") throw new Error(response.error ?? `HIE host command failed: ${command}`);
    };
    return {
      openMedia: () => requireOk("open_media", { requestId: requestId() }),
      exportDocument: () => requireOk("export_document", { requestId: requestId() }),
      notify: (message: string) => { void requireOk("notify", { requestId: requestId(), message }); },
    };
  }
  return browserHost;
}
