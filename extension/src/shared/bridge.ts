/**
 * Client for the Image Toolkit desktop-app bridge (§7.5A / §7.6 / §7.8).
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

export interface SimilarMatch {
  path: string;
  /** 1.0 = identical, 0.0 = maximally different (64-bit pHash Hamming distance, normalized). */
  score: number;
  hamming: number;
  width: number | null;
  height: number | null;
  thumb_b64: string | null;
}

export interface SimilarResult {
  results: SimilarMatch[];
  scanned: number;
  cold_scan: boolean;
  /**
   * Ranking method actually used. Currently always `"phash"` — the app's
   * embedding index (BGE-M3/CLIP, §7.8's ideal path) isn't populated yet,
   * so this degrades to perceptual-hash ranking per the roadmap's explicit
   * fallback clause. A future embedding-based server response keeps this
   * same shape (e.g. `method: "embedding"`).
   */
  method: string;
}

/**
 * Ranked visual-similarity search against the app's library (§7.8).
 * "Find similar in my library" — returns up to `topK` results ranked
 * closest-first, unlike `dupCheck` which only returns matches within a
 * duplicate threshold.
 */
export function findSimilar(
  imageUrl: string,
  topK = 12,
): Promise<SimilarResult> {
  return bridgeFetch<SimilarResult>("/similar/", {
    method: "POST",
    body: JSON.stringify({ url: imageUrl, top_k: topK }),
  });
}

export interface IngestResult {
  path: string;
}

/**
 * Ingest an image into the app's library with provenance metadata (§7.7).
 * Throws BridgeError with status 409 when the image is already in the
 * library (the server includes the existing paths in its message).
 */
export function ingest(
  imageUrl: string,
  pageUrl?: string,
  pageTitle?: string,
): Promise<IngestResult> {
  return bridgeFetch<IngestResult>("/ingest/", {
    method: "POST",
    body: JSON.stringify({
      url: imageUrl,
      source_page_url: pageUrl,
      page_title: pageTitle,
    }),
  });
}
