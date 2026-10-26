/**
 * Host communication seam for the Hybrid Image Editor (HIE).
 */

export interface HieHostCapabilities {
  version: string;
  hasHardwareAcceleration: boolean;
  supportedFileTypes: string[];
}

export interface HieHost {
  openMedia(): Promise<{ documentId?: string } | null>;
  exportDocument(documentId?: string): Promise<boolean>;
  notify(message: string): void;
  listCapabilities?(): Promise<HieHostCapabilities>;
  previewPolicy?(policyName: string): Promise<Record<string, unknown>>;
  acceptProposal?(proposalId: string): Promise<boolean>;
  submitRestoration?(documentId: string, model: string): Promise<{ taskId: string }>;
}

class BrowserFallbackHieHost implements HieHost {
  async openMedia(): Promise<{ documentId: string }> {
    return { documentId: `doc-${Date.now().toString(16)}` };
  }

  async exportDocument(): Promise<boolean> {
    return true;
  }

  notify(message: string): void {
    if (typeof console !== "undefined") {
      console.log(`[HIE Host] ${message}`);
    }
  }

  async listCapabilities(): Promise<HieHostCapabilities> {
    return {
      version: "2.0.0-embedded",
      hasHardwareAcceleration: true,
      supportedFileTypes: ["png", "jpg", "jpeg", "webp", "tiff", "mp4", "webm"],
    };
  }

  async previewPolicy(policyName: string): Promise<Record<string, unknown>> {
    return { policy: policyName, confidence: 0.94, ready: true };
  }

  async acceptProposal(): Promise<boolean> {
    return true;
  }

  async submitRestoration(documentId: string, model: string): Promise<{ taskId: string }> {
    return { taskId: `task-${documentId}-${model}-${Date.now().toString(16)}` };
  }
}

export function getHieHost(): HieHost {
  const customHost =
    typeof window !== "undefined"
      ? (window as unknown as { __HIE_HOST__?: HieHost }).__HIE_HOST__
      : undefined;
  if (customHost) {
    return customHost;
  const injected = (window as { __HIE_HOST__?: HieHost } | undefined)?.__HIE_HOST__;
  if (typeof window !== "undefined" && injected) {
    return injected;
  }
  return new BrowserFallbackHieHost();
}
