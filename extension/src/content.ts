/**
 * Content script — Turbo Mode.
 *
 * When enabled, intercepts pointer events in the capture phase, finds the
 * image under the cursor (even beneath overlays) and asks the background
 * worker to download it, while blocking the site's own handlers.
 */
import { api, storageGet } from "./shared/api";
import { findImageAt } from "./shared/extractor";
import type { DownloadImageMsg } from "./shared/messages";

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

// Intercept all relevant pointer/touch events to prevent site logic (like zoom/pan)
const blockAndDownload = (e: Event): void => {
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
