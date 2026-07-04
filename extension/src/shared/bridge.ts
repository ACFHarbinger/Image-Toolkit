/**
 * Client for the Image Toolkit desktop-app bridge (§7.5A / §7.6).
 *
 * Talks to the token-authenticated localhost Django endpoints under
 * `/api/extension/`. All functions throw `BridgeError` on transport or
 * HTTP-level failures so callers can degrade gracefully.
 */
import { loadSettings } from "./settings";

export class BridgeError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

export interface PingResult {
  version: string;
  features: string[];
  dup_root_configured: boolean;
}

export interface DupMatch {
  path: string;
  hamming: number;
  width: number | null;
  height: number | null;
  thumb_b64: string | null;
}

export interface DupCheckResult {
  matches: DupMatch[];
  scanned: number;
  cold_scan: boolean;
  threshold: number;
}

async function bridgeFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const settings = await loadSettings();
  const base = settings.bridgeUrl.replace(/\/+$/, "");
  let resp: Response;
  try {
    resp = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${settings.bridgeToken}`,
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    throw new BridgeError(
      `Image Toolkit is not reachable at ${base} (${String(err)})`,
    );
  }
  if (!resp.ok) {
    let detail = "";
    try {
      const body = (await resp.json()) as { error?: string; detail?: string };
      detail = body.error ?? body.detail ?? "";
    } catch {
      /* non-JSON body */
    }
    throw new BridgeError(detail || `HTTP ${resp.status}`, resp.status);
  }
  return (await resp.json()) as T;
}

/** Liveness + feature discovery; also validates the pairing token. */
export function ping(): Promise<PingResult> {
  return bridgeFetch<PingResult>("/ping/");
}

/** Perceptual duplicate search of the app's configured directory tree. */
export function dupCheck(imageUrl: string): Promise<DupCheckResult> {
  return bridgeFetch<DupCheckResult>("/dup-check/", {
    method: "POST",
    body: JSON.stringify({ url: imageUrl }),
  });
}
