import { invoke } from "@tauri-apps/api/core";

/**
 * Security and origin isolation for embedded ComfyUI (#890, S-04).
 *
 * Ensures ComfyUI is confined to an isolated view with zero native privileges
 * (no window.__TAURI__ access, strict iframe sandbox, local-origin confinement,
 * and seamless fallback to the external default browser).
 */

export interface ComfyValidationResult {
  valid: boolean;
  error?: string;
}

export interface ComfyCompatibilityResult {
  embeddable: boolean;
  checked: boolean;
  reason?: string;
  wsUrl?: string;
}

/**
 * Validates that the provided ComfyUI URL is strictly confined to a local loopback origin.
 * Remote origins, credentials, and non-HTTP protocols are strictly rejected.
 */
export function validateComfyOrigin(urlString: string): ComfyValidationResult {
  if (!urlString || typeof urlString !== "string") {
    return { valid: false, error: "ComfyUI URL is required." };
  }

  let url: URL;
  try {
    url = new URL(urlString.trim());
  } catch {
    return { valid: false, error: "Invalid URL format." };
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { valid: false, error: `Protocol '${url.protocol}' is not allowed; must be http or https.` };
  }

  if (url.username || url.password) {
    return { valid: false, error: "Embedded ComfyUI URLs must not contain embedded user credentials." };
  }

  const hostname = url.hostname.toLowerCase();
  const isLoopback =
    hostname === "127.0.0.1" ||
    hostname === "localhost" ||
    hostname === "::1" ||
    hostname === "[::1]";

  if (!isLoopback) {
    return {
      valid: false,
      error: `Origin '${hostname}' rejected. Embedded ComfyUI must run on a local loopback interface (127.0.0.1 or localhost).`,
    };
  }

  return { valid: true };
}

/**
 * Builds the corresponding WebSocket endpoint for live queue progress.
 */
export function buildComfyWebSocketUrl(httpUrlString: string): string {
  const url = new URL(httpUrlString);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${url.host}/ws`;
}

/**
 * Checks HTTP headers returned from the ComfyUI server for iframe embedding restrictions
 * (e.g. X-Frame-Options: DENY / SAMEORIGIN or CSP: frame-ancestors).
 */
export function checkEmbeddingCompatibility(
  urlString: string,
  headers?: Record<string, string>,
): ComfyCompatibilityResult {
  const validation = validateComfyOrigin(urlString);
  if (!validation.valid) {
    return { embeddable: false, checked: true, reason: validation.error };
  }

  if (!headers) {
    return { embeddable: false, checked: false, reason: "Embedding headers were not probed." };
  }

  if (headers) {
    const normHeaders: Record<string, string> = {};
    for (const [k, v] of Object.entries(headers)) {
      normHeaders[k.toLowerCase()] = v.toLowerCase();
    }

    const xfo = normHeaders["x-frame-options"];
    if (xfo) {
      if (xfo.includes("deny")) {
        return {
          embeddable: false,
          checked: true,
          reason: "ComfyUI server configured with 'X-Frame-Options: DENY', which blocks iframe embedding.",
        };
      }
      if (xfo.includes("sameorigin")) {
        return {
          embeddable: false,
          checked: true,
          reason: "ComfyUI server configured with 'X-Frame-Options: SAMEORIGIN', blocking cross-origin Tauri embedding.",
        };
      }
    }

    const csp = normHeaders["content-security-policy"];
    if (csp && csp.includes("frame-ancestors")) {
      if (csp.includes("frame-ancestors 'none'") || csp.includes("frame-ancestors 'self'")) {
        return {
          embeddable: false,
          checked: true,
          reason: `ComfyUI CSP directive '${csp}' prohibits embedding in Tauri.`,
        };
      }
    }
  }

  return {
    embeddable: true,
    checked: true,
    wsUrl: buildComfyWebSocketUrl(urlString),
  };
}

/** Read embedding headers from the Comfy server. A failure is not a successful probe. */
export async function probeEmbeddingHeaders(urlString: string): Promise<Record<string, string>> {
  const validation = validateComfyOrigin(urlString);
  if (!validation.valid) {
    throw new Error(validation.error ?? "invalid ComfyUI URL");
  }
  const response = await fetch(urlString, { method: "GET" });
  const headers: Record<string, string> = {};
  response.headers.forEach((value, key) => {
    headers[key] = value;
  });
  return headers;
}

/**
 * Generates the strict HTML5 iframe sandbox permission string.
 * Native Tauri privileges (allow-modals, allow-top-navigation, allow-same-origin with full access)
 * are restricted, while allowing scripts, forms, downloads, and canvas operations.
 */
export function getComfySandboxPermissions(): string {
  return "allow-scripts allow-forms allow-same-origin allow-downloads";
}

/**
 * Opens ComfyUI in the user's external default system browser.
 */
export async function openExternalBrowser(url: string): Promise<boolean> {
  const validation = validateComfyOrigin(url);
  if (!validation.valid) {
    throw new Error(validation.error);
  }

  await invoke("open_comfy_browser", { url: new URL(url.trim()).href });
  return true;
}
