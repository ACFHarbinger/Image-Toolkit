/**
 * Content script — Turbo Mode.
 *
 * When enabled, intercepts pointer events in the capture phase, finds the
 * image under the cursor (even beneath overlays) and asks the background
 * worker to download it, while blocking the site's own handlers.
 */
import { api, storageGet } from "./shared/api";
import { findImageAt } from "./shared/extractor";
import { collectPageMedia } from "./shared/pageMedia";
import {
  startSelectionOverlay,
  overlayActive,
} from "./contentOverlay";
import {
  captureVideoFrames,
  rememberContextTarget,
} from "./videoCapture";
import type {
  DownloadImageMsg,
  DownloadBatchMsg,
  ExtensionMessage,
  PageCaptureResponse,
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

// Initial check
void storageGet<{ turboMode: boolean }>(["turboMode"]).then((result) => {
  turboMode = result.turboMode ?? false;
});

// Listen for storage changes to update dynamically
api.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.turboMode) {
    turboMode = Boolean(changes.turboMode.newValue);
  }
});

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

// --- Bulk page capture (§7.9) ---

api.runtime.onMessage.addListener(
  (
    request: ExtensionMessage,
    _sender,
    sendResponse: (r: PageCaptureResponse) => void,
  ) => {
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
    return false;
  },
);

// Intercept all relevant pointer/touch events to prevent site logic (like zoom/pan)
const blockAndDownload = (e: Event): void => {
  // The selection overlay owns clicks while it is active (§7.9B)
  if (overlayActive()) return;
  if (!turboMode) return;

  // For mouse events, only handle main button (Left Click)
  if (e.type.startsWith("mouse") && (e as MouseEvent).button !== 0) return;

  const me = e as MouseEvent & TouchEvent;
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
