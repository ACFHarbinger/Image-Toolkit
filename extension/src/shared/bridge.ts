/**
 * Client for the Image Toolkit desktop-app bridge (§7.5 / §7.6 / §7.8).
 *
 * Two transports, selected by `settings.bridgeTransport`, behind one set of
 * exported functions — callers never branch on transport:
 * - **"http"** (§7.5A, default): token-authenticated localhost Django
 *   endpoints under `/api/extension/`.
 * - **"native"** (§7.5B): `runtime.sendNativeMessage` to the
 *   `extension_api/native_host.py` process, installed per-browser via
 *   `desktop/linux/scripts/install_native_host.sh`. No token — the
 *   browser's own native-messaging host-manifest allowlist is the security
 *   boundary instead.
 *
 * All functions throw `BridgeError` on transport or request-level failures
 * so callers can degrade gracefully regardless of which transport is active.
 */
import { sendNativeMessage } from "./api";
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

/** Shape returned by `native_host.py::dispatch` for every action. */
interface NativeResponse<T> {
  ok: boolean;
  status: number;
  body: T & { error?: string };
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

/**
 * Send one `{action, payload}` native message and unwrap it into the same
 * success/`BridgeError` shape `bridgeFetch` produces, so every exported
 * function below can share one code path per transport branch.
 */
async function bridgeNative<T>(
  action: string,
  payload: Record<string, unknown> = {},
): Promise<T> {
  const settings = await loadSettings();
  let response: NativeResponse<T>;
  try {
    response = await sendNativeMessage<NativeResponse<T>>(
      settings.nativeHostName,
      { action, payload },
    );
  } catch (err) {
    throw new BridgeError(
      `Native messaging host '${settings.nativeHostName}' is not reachable ` +
        `(${String(err)}) — has it been installed? See ` +
        "desktop/linux/scripts/install_native_host.sh.",
    );
  }
  if (!response || !response.ok) {
    throw new BridgeError(
      response?.body?.error || `Native host error (status ${response?.status})`,
      response?.status,
    );
  }
  return response.body as T;
}

/** Dispatches to whichever transport `settings.bridgeTransport` selects. */
async function bridgeCall<T>(
  action: string,
  httpPath: string,
  payload: Record<string, unknown>,
): Promise<T> {
  const settings = await loadSettings();
  if (settings.bridgeTransport === "native") {
    return bridgeNative<T>(action, payload);
  }
  const isGet = action === "ping" || action === "phash_snapshot";
  return bridgeFetch<T>(httpPath, {
    method: isGet ? "GET" : "POST",
    ...(isGet ? {} : { body: JSON.stringify(payload) }),
  });
}

/** Liveness + feature discovery; also validates the pairing token (http) / manifest (native). */
export function ping(): Promise<PingResult> {
  return bridgeCall<PingResult>("ping", "/ping/", {});
}

/** Perceptual duplicate search of the app's configured directory tree. */
export function dupCheck(imageUrl: string): Promise<DupCheckResult> {
  return bridgeCall<DupCheckResult>("dup_check", "/dup-check/", {
    url: imageUrl,
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
  return bridgeCall<SimilarResult>("similar", "/similar/", {
    url: imageUrl,
    top_k: topK,
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
  return bridgeCall<IngestResult>("ingest", "/ingest/", {
    url: imageUrl,
    source_page_url: pageUrl,
    page_title: pageTitle,
  });
}

export interface PhashSnapshotResult {
  /** Sorted, deduplicated 16-hex-digit (64-bit) pHashes. No file paths —
   * the snapshot is cached client-side, so only the minimum needed for an
   * approximate Hamming-distance sweep leaves the app. */
  hashes: string[];
  count: number;
  scanned: number;
  cold_scan: boolean;
  generated_at: string;
}

/**
 * §7.16C — fetch the app's current pHash set for client-side caching.
 * Pairs with `clientPhash.ts`'s local snapshot store: call this
 * periodically (or on demand) to refresh `storage.local`, then use
 * `snapshotBestMatch()` for instant, no-round-trip "probably already have
 * this" hints. The authoritative check remains `dupCheck()`.
 */
export function getPhashSnapshot(): Promise<PhashSnapshotResult> {
  return bridgeCall<PhashSnapshotResult>(
    "phash_snapshot",
    "/phash-snapshot/",
    {},
  );
}
