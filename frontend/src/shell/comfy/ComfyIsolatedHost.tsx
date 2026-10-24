import React, { useEffect, useState } from "react";
import {
  checkEmbeddingCompatibility,
  ComfyCompatibilityResult,
  getComfySandboxPermissions,
  openExternalBrowser,
  probeEmbeddingHeaders,
  validateComfyOrigin,
} from "./comfySecurity";

export interface ComfyIsolatedHostProps {
  comfyUrl?: string;
  initialHeaders?: Record<string, string>;
  probeHeaders?: (url: string) => Promise<Record<string, string>>;
  onFallbackToBrowser?: (url: string) => void;
}

export function ComfyIsolatedHost({
  comfyUrl = "http://127.0.0.1:8188",
  initialHeaders,
  probeHeaders = probeEmbeddingHeaders,
  onFallbackToBrowser,
}: ComfyIsolatedHostProps): React.ReactElement {
  const [url, setUrl] = useState(comfyUrl);
  const [status, setStatus] = useState<"checking" | "ready" | "blocked" | "error">("checking");
  const [compat, setCompat] = useState<ComfyCompatibilityResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    const val = validateComfyOrigin(url);
    if (!val.valid) {
      setStatus("error");
      setCompat({ embeddable: false, checked: true, reason: val.error });
      return;
    }

    setStatus("checking");
    const inspect = async () => {
      try {
        const headers = initialHeaders ?? (await probeHeaders(url));
        if (cancelled) {
          return;
        }
        const res = checkEmbeddingCompatibility(url, headers);
        setCompat(res);
        setStatus(res.embeddable ? "ready" : "blocked");
      } catch (err) {
        if (cancelled) {
          return;
        }
        setCompat({
          embeddable: false,
          checked: false,
          reason: err instanceof Error ? err.message : "Embedding probe failed.",
        });
        setStatus("blocked");
      }
    };
    void inspect();
    return () => {
      cancelled = true;
    };
  }, [url, initialHeaders, probeHeaders]);

  const handleOpenExternal = async () => {
    onFallbackToBrowser?.(url);
    await openExternalBrowser(url);
  };

  return (
    <div
      data-testid="comfy-isolated-host"
      className="flex h-full w-full flex-col rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      {/* Control & Security Status Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2.5 dark:border-gray-800 dark:bg-gray-900/60">
        <div className="flex items-center gap-3">
          <span className="text-base">🎨</span>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-800 dark:text-gray-200">ComfyUI Host</span>
            <span
              data-testid="comfy-isolation-badge"
              className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300"
            >
              🔒 Isolated Sandbox • Zero Native Privileges
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            data-testid="comfy-url-input"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-56 rounded border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
            placeholder="http://127.0.0.1:8188"
          />
          <button
            type="button"
            data-testid="btn-open-external"
            onClick={handleOpenExternal}
            className="rounded border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            title="Open in external system browser"
          >
            External Browser ↗
          </button>
        </div>
      </header>

      {/* Main View Area */}
      <div className="relative flex-1 overflow-hidden bg-gray-100 dark:bg-black">
        {status === "checking" && (
          <div className="flex h-full items-center justify-center text-xs text-gray-500">
            Checking ComfyUI compatibility and origin isolation...
          </div>
        )}

        {status === "error" && (
          <div
            data-testid="comfy-error-banner"
            className="m-6 rounded-lg border border-red-300 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950/50"
          >
            <span className="text-2xl">⚠</span>
            <h3 className="mt-2 text-sm font-bold text-red-800 dark:text-red-200">
              Security Violation or Invalid URL
            </h3>
            <p className="mt-1 text-xs text-red-700 dark:text-red-300">{compat?.reason}</p>
          </div>
        )}

        {status === "blocked" && (
          <div
            data-testid="comfy-blocked-banner"
            className="m-6 rounded-lg border border-amber-300 bg-amber-50 p-6 text-center dark:border-amber-800 dark:bg-amber-950/50"
          >
            <span className="text-2xl">🛡</span>
            <h3 className="mt-2 text-sm font-bold text-amber-800 dark:text-amber-200">
              Embedding Blocked by Server Security Headers
            </h3>
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{compat?.reason}</p>
            <div className="mt-4">
              <button
                type="button"
                data-testid="btn-fallback-external"
                onClick={handleOpenExternal}
                className="rounded-lg bg-amber-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-amber-700"
              >
                Launch in Default Browser Instead 🚀
              </button>
            </div>
          </div>
        )}

        {status === "ready" && (
          <iframe
            data-testid="comfy-isolated-iframe"
            title="ComfyUI Isolated Workspace"
            src={url}
            onError={() => {
              setStatus("blocked");
              setCompat({
                embeddable: false,
                checked: true,
                reason: "The ComfyUI frame failed to load.",
              });
            }}
            sandbox={getComfySandboxPermissions()}
            allow="clipboard-read; clipboard-write; fullscreen"
            className="h-full w-full border-0"
          />
        )}
      </div>

      {/* Footer Info */}
      <footer className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-1.5 text-[10px] text-gray-500 dark:border-gray-800 dark:bg-gray-900/60 dark:text-gray-400">
        <div>
          WebSocket Stream:{" "}
          <span className="font-mono text-gray-700 dark:text-gray-300">{compat?.wsUrl ?? "—"}</span>
        </div>
        <div>Tauri IPC Bridge: <span className="font-semibold text-emerald-600 dark:text-emerald-400">Disabled (Zero Native Access)</span></div>
      </footer>
    </div>
  );
}
