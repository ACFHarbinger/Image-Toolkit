/** Typed host seam shared by standalone Vite, Tauri, and Image-Toolkit tabs. */

import { invoke } from "@tauri-apps/api/core";

export interface HieCapabilities {
  models: string[];
  policies: string[];
  restoration: Record<string, string[]>;
}

export interface HieHost {
  openMedia(source?: string): Promise<{ documentId?: string } | void>;
  exportDocument(documentId?: string): Promise<void>;
  notify(message: string): void;
  listCapabilities?(documentId?: string): Promise<HieCapabilities>;
  previewPolicy?(documentId: string, policy: string): Promise<void>;
  acceptProposal?(documentId: string): Promise<void>;
}

interface IpcResponse {
  version: number;
  request_id: string;
  status: "ok" | "error";
  payload: Record<string, unknown>;
  error: string | null;
}

function requestId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `hie-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
}

const browserHost: HieHost = {
  async openMedia(): Promise<{ documentId?: string } | void> {
    // Browser-safe fallback; Tauri/Image-Toolkit hosts replace this method.
    return { documentId: undefined };
  },
  async exportDocument(): Promise<void> {
    // Browser-safe fallback; Tauri/Image-Toolkit hosts replace this method.
  },
  notify(message: string): void {
    console.info(`[HIE] ${message}`);
  },
  async listCapabilities(): Promise<HieCapabilities> {
    return {
      models: [],
      policies: ["localized_tone", "adjust_exposure", "crop"],
      restoration: {},
    };
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
    const requireOk = async (
      command: string,
      args: Record<string, string>
    ): Promise<Record<string, unknown>> => {
      const response = await invoke<IpcResponse>(command, args);
      if (response.status === "error") {
        throw new Error(response.error ?? `HIE host command failed: ${command}`);
      }
      return response.payload ?? {};
    };
    return {
      openMedia: async (source?: string) => {
        const payload = await requireOk("open_media", {
          requestId: requestId(),
          ...(source ? { source } : {}),
        });
        return { documentId: payload.document_id as string | undefined };
      },
      exportDocument: async (documentId?: string) => {
        await requireOk("export_document", {
          requestId: requestId(),
          ...(documentId ? { documentId } : {}),
        });
      },
      notify: (message: string) => {
        void requireOk("notify", { requestId: requestId(), message });
      },
      listCapabilities: async (documentId?: string) => {
        const payload = await requireOk("list_capabilities", {
          requestId: requestId(),
          ...(documentId ? { documentId } : {}),
        });
        return {
          models: (payload.models as string[]) ?? [],
          policies: (payload.policies as string[]) ?? [],
          restoration: (payload.restoration as Record<string, string[]>) ?? {},
        };
      },
      previewPolicy: async (documentId: string, policy: string) => {
        await requireOk("preview_policy", {
          requestId: requestId(),
          documentId,
          policy,
        });
      },
      acceptProposal: async (documentId: string) => {
        await requireOk("accept_proposal", {
          requestId: requestId(),
          documentId,
        });
      },
    };
  }
  return browserHost;
}
