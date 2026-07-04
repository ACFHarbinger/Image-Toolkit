/**
 * Content script — Turbo Mode.
 *
 * When enabled, intercepts pointer events in the capture phase, finds the
 * image under the cursor (even beneath overlays) and asks the background
 * worker to download it, while blocking the site's own handlers.
 */
import { api, storageGet } from "./shared/api";
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

// Intercept all relevant pointer/touch events to prevent site logic (like zoom/pan)
const blockAndDownload = (e: Event): void => {
  if (!turboMode) return;

  // For mouse events, only handle main button (Left Click)
  if (e.type.startsWith("mouse") && (e as MouseEvent).button !== 0) return;

  const me = e as MouseEvent & TouchEvent;
  const x = me.clientX ?? me.touches?.[0]?.clientX ?? 0;
  const y = me.clientY ?? me.touches?.[0]?.clientY ?? 0;

  // Use elementsFromPoint to find images even under overlays
  const elements = document.elementsFromPoint(x, y);
  let targetImage: HTMLImageElement | null = null;

  for (const el of elements) {
    if (el.tagName === "IMG" && (el as HTMLImageElement).src) {
      targetImage = el as HTMLImageElement;
      break;
    }
  }

  if (targetImage) {
    // Stop the event from reaching the site's elements or bubbling up
    e.stopPropagation();
    e.stopImmediatePropagation();

    // For 'click', we also prevent default (to stop links/zoom) and trigger download
    if (e.type === "click") {
      e.preventDefault();

      const msg: DownloadImageMsg = {
        action: "download_image",
        src: targetImage.src,
      };
      void api.runtime.sendMessage(msg);
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
