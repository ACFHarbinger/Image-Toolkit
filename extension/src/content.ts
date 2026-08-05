/**
 * Content script — Turbo Mode.
 *
 * When enabled, intercepts pointer events in the capture phase, finds the
 * image under the cursor (even beneath overlays) and asks the background
 * worker to download it, while blocking the site's own handlers.
 */
import { api, storageGet } from "./shared/api";
import {
  applyUrlUpgrade,
  backgroundImageUrl,
  bestImageUrl,
  canvasDataUrl,
  findImageAt,
} from "./shared/extractor";
import { isTurboActiveOnSite } from "./shared/naming";
import type { ExtensionSettings } from "./shared/settings";
import { collectPageMedia, collectImageDetails } from "./shared/pageMedia";
import {
  startSelectionOverlay,
  overlayActive,
} from "./contentOverlay";
import {
  captureVideoFrames,
  getContextTarget,
  rememberContextTarget,
} from "./videoCapture";
import { captureVideoClip } from "./videoClip";
import type {
  DownloadImageMsg,
  DownloadBatchMsg,
  ExtensionMessage,
  PageCaptureResponse,
  ResolveContextImageResponse,
  CollectPageImagesResponse,
  CaptureVideoClipResponse,
} from "./shared/messages";

// Track the element under the last context-menu so video capture can find
// the exact <video> the user right-clicked (§7.15A).
document.addEventListener(
  "contextmenu",
  (e) => rememberContextTarget(e.target as Element),
  true,
);

console.log(`[Image-Toolkit] Content script loaded on: ${window.location.href}`);

let turboMode = false;
let turboModifierKey: ExtensionSettings["turboModifierKey"] = "none";
let turboActiveHere = true;

type TurboGatingKeys = "turboMode" | "turboModifierKey" | "turboSiteMode" | "turboSitePatterns";

function recomputeTurboGating(settings: Partial<ExtensionSettings>): void {
  if (settings.turboMode !== undefined) turboMode = settings.turboMode;
  if (settings.turboModifierKey !== undefined) turboModifierKey = settings.turboModifierKey;
  turboActiveHere = isTurboActiveOnSite(window.location.hostname, {
    turboSiteMode: settings.turboSiteMode ?? "all",
    turboSitePatterns: settings.turboSitePatterns ?? [],
  });
}

// Initial check
void storageGet<Pick<ExtensionSettings, TurboGatingKeys>>([
  "turboMode",
  "turboModifierKey",
  "turboSiteMode",
  "turboSitePatterns",
]).then(recomputeTurboGating);

// Listen for storage changes to update dynamically
api.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  const patch: Partial<ExtensionSettings> = {};
  if (changes.turboMode) patch.turboMode = Boolean(changes.turboMode.newValue);
  if (changes.turboModifierKey) {
    patch.turboModifierKey = changes.turboModifierKey.newValue as ExtensionSettings["turboModifierKey"];
  }
  if (changes.turboSiteMode) {
    patch.turboSiteMode = changes.turboSiteMode.newValue as ExtensionSettings["turboSiteMode"];
  }
  if (changes.turboSitePatterns) {
    patch.turboSitePatterns = changes.turboSitePatterns.newValue as string[];
  }
  if (Object.keys(patch).length > 0) recomputeTurboGating(patch);
});

/** Live cursor feedback while the configured modifier key is held (§7.12). */
const MODIFIER_CURSOR_CLASS = "image-toolkit-modifier-capture";
let modifierStyleEl: HTMLStyleElement | null = null;

function ensureModifierStyle(): void {
  if (modifierStyleEl) return;
  modifierStyleEl = document.createElement("style");
  modifierStyleEl.textContent =
    `html.${MODIFIER_CURSOR_CLASS}, html.${MODIFIER_CURSOR_CLASS} * { cursor: crosshair !important; }`;
  document.documentElement.appendChild(modifierStyleEl);
}

function isConfiguredModifierEvent(e: KeyboardEvent): boolean {
  if (turboModifierKey === "alt") return e.key === "Alt";
  if (turboModifierKey === "ctrl") return e.key === "Control";
  if (turboModifierKey === "shift") return e.key === "Shift";
  return false;
}

document.addEventListener("keydown", (e) => {
  if (!turboActiveHere || !isConfiguredModifierEvent(e)) return;
  ensureModifierStyle();
  document.documentElement.classList.add(MODIFIER_CURSOR_CLASS);
});
document.addEventListener("keyup", (e) => {
  if (!isConfiguredModifierEvent(e)) return;
  document.documentElement.classList.remove(MODIFIER_CURSOR_CLASS);
});
window.addEventListener("blur", () => {
  document.documentElement.classList.remove(MODIFIER_CURSOR_CLASS);
});

/** Whether *e* carries the configured modifier key (§7.12). "none" always misses. */
function modifierHeld(e: MouseEvent): boolean {
  if (turboModifierKey === "alt") return e.altKey;
  if (turboModifierKey === "ctrl") return e.ctrlKey;
  if (turboModifierKey === "shift") return e.shiftKey;
  return false;
}

/** Brief outline flash on the captured element (§7.12 capture feedback). */
const flashCaptured = (el: Element): void => {
  const h = el as HTMLElement;
  if (!h.style) return;
  const prevOutline = h.style.outline;
  const prevOffset = h.style.outlineOffset;
  h.style.outline = "3px solid #2ecc71";
  h.style.outlineOffset = "-3px";
  setTimeout(() => {
    h.style.outline = prevOutline;
    h.style.outlineOffset = prevOffset;
  }, 450);
};

/**
 * Re-resolve the best URL for the element the user last right-clicked
 * (§7.11 context-menu correlation) — an <img> right-click only gives the
 * background worker `info.srcUrl`, the raw (often thumbnail) URL, with no
 * access to the DOM to check srcset/lazy-load attrs or the URL-upgrade
 * table; a <canvas> right-click gives no `srcUrl` at all. Falls back to
 * `fallbackUrl` when the remembered target doesn't resolve to anything
 * better (e.g. the page navigated since the right-click).
 */
function resolveContextImageUrl(fallbackUrl: string): string {
  const target = getContextTarget();
  if (target instanceof HTMLImageElement && target.src) {
    return bestImageUrl(target);
  }
  if (target instanceof HTMLCanvasElement) {
    const dataUrl = canvasDataUrl(target);
    if (dataUrl) return dataUrl;
  }
  if (target) {
    const bg = backgroundImageUrl(target);
    if (bg) return bg;
  }
  return applyUrlUpgrade(fallbackUrl);
}

// --- Bulk page capture (§7.9) ---

api.runtime.onMessage.addListener(
  (
    request: ExtensionMessage,
    _sender,
    sendResponse: (
      r:
        | PageCaptureResponse
        | ResolveContextImageResponse
        | CollectPageImagesResponse
        | CaptureVideoClipResponse,
    ) => void,
  ) => {
    if (request.action === "collect_page_images") {
      sendResponse({
        ok: true,
        pageUrl: window.location.href,
        images: collectImageDetails(),
      });
      return false;
    }
    if (request.action === "download_all_media") {
      const media = collectPageMedia();
      const urls = [...media.images, ...media.videos];
      if (urls.length > 0) {
        const msg: DownloadBatchMsg = {
          action: "download_batch",
          urls,
          pageUrl: window.location.href,
        };
        void api.runtime.sendMessage(msg);
      }
      sendResponse({
        ok: true,
        images: media.images.length,
        videos: media.videos.length,
      });
      return false;
    }
    if (request.action === "start_selection_overlay") {
      startSelectionOverlay();
      sendResponse({ ok: true });
      return false;
    }
    if (request.action === "capture_video_frame") {
      void captureVideoFrames(request).then((r) =>
        sendResponse(r as PageCaptureResponse),
      );
      return true; // async response
    }
    if (request.action === "resolve_context_image") {
      sendResponse({ url: resolveContextImageUrl(request.srcUrl) });
      return false;
    }
    if (request.action === "capture_video_clip") {
      void captureVideoClip(request).then(sendResponse);
      return true; // async response
    }
    return false;
  },
);

// Intercept all relevant pointer/touch events to prevent site logic (like zoom/pan)
const blockAndDownload = (e: Event): void => {
  // The selection overlay owns clicks while it is active (§7.9B)
  if (overlayActive()) return;
  if (!turboActiveHere) return;

  const me = e as MouseEvent & TouchEvent;
  // Active if the global toggle is on, OR the configured modifier key
  // (§7.12) is held for this click — a scoped alternative that doesn't
  // require enabling interception globally.
  if (!turboMode && !modifierHeld(me)) return;

  // For mouse events, only handle main button (Left Click)
  if (e.type.startsWith("mouse") && (e as MouseEvent).button !== 0) return;

  const x = me.clientX ?? me.touches?.[0]?.clientX ?? 0;
  const y = me.clientY ?? me.touches?.[0]?.clientY ?? 0;

  // Find the image under the cursor, even beneath overlays; upgrades to the
  // largest srcset/lazy-load candidate and falls back to CSS backgrounds (§7.11).
  const hit = findImageAt(x, y);

  if (hit) {
    // Stop the event from reaching the site's elements or bubbling up
    e.stopPropagation();
    e.stopImmediatePropagation();

    // For 'click', we also prevent default (to stop links/zoom) and trigger download
    if (e.type === "click") {
      e.preventDefault();

      const msg: DownloadImageMsg = {
        action: "download_image",
        src: hit.url,
        pageUrl: window.location.href,
        source: "turbo",
      };
      void api.runtime.sendMessage(msg);
      flashCaptured(hit.element);
    }
  }
};

// Listen to all phases that might trigger site logic
const events = [
  "click",
  "mousedown",
  "mouseup",
  "pointerdown",
  "pointerup",
  "touchstart",
  "touchend",
];
for (const eventType of events) {
  document.addEventListener(eventType, blockAndDownload, {
    capture: true,
    passive: false,
  });
}
