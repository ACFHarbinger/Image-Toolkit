/** Typed host seam shared by standalone Vite, Tauri, and Image-Toolkit tabs. */

import { invoke } from "@tauri-apps/api/core";

export interface HieHost {
  openMedia(): Promise<void>;
  exportDocument(): Promise<void>;
  notify(message: string): void;
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
    return {
      openMedia: () => invoke("open_media"),
      exportDocument: () => invoke("export_document"),
      notify: (message: string) => { void invoke("notify", { message }); },
    };
  }
  return browserHost;
}
