/**
 * In-page image selection overlay (§7.9B).
 *
 * Entered via the popup's "Select images on page…" button. Images highlight
 * on hover; clicking toggles selection (site handlers are suppressed while
 * the overlay is active). A floating action bar shows the live count with
 * Download / Cancel buttons; Esc cancels.
 */
import { api } from "./shared/api";
import { bestImageUrl } from "./shared/extractor";
import type { DownloadBatchMsg } from "./shared/messages";

const BAR_ID = "__imgtk_select_bar";
const Z_MAX = "2147483647";

const HOVER_OUTLINE = "3px dashed #3498db";
const SELECTED_OUTLINE = "3px solid #2ecc71";

interface OverlayState {
  selected: Set<HTMLImageElement>;
  savedOutline: Map<HTMLImageElement, string>;
  hovered: HTMLImageElement | null;
  bar: HTMLDivElement;
  countEl: HTMLSpanElement;
  listeners: Array<[string, EventListener, boolean | AddEventListenerOptions]>;
}

let state: OverlayState | null = null;

/** True while the selection overlay is active (turbo mode must stand down). */
export function overlayActive(): boolean {
  return state !== null;
}

function setOutline(img: HTMLImageElement, outline: string | null): void {
  const st = state;
  if (!st) return;
  if (!st.savedOutline.has(img)) {
    st.savedOutline.set(img, img.style.outline);
  }
  img.style.outline = outline ?? st.savedOutline.get(img) ?? "";
  img.style.outlineOffset = outline ? "-3px" : "";
}

function refreshCount(): void {
  if (!state) return;
  const n = state.selected.size;
  state.countEl.textContent = `${n} image${n === 1 ? "" : "s"} selected`;
}

function imageAt(e: MouseEvent): HTMLImageElement | null {
  for (const el of document.elementsFromPoint(e.clientX, e.clientY)) {
    if (el.id === BAR_ID || (el as HTMLElement).closest?.(`#${BAR_ID}`)) {
      return null; // never treat the action bar as content
    }
    if (el.tagName === "IMG") return el as HTMLImageElement;
  }
  return null;
}

function onMouseMove(e: Event): void {
  const st = state;
  if (!st) return;
  const img = imageAt(e as MouseEvent);
  if (img === st.hovered) return;
  if (st.hovered && !st.selected.has(st.hovered)) setOutline(st.hovered, null);
  st.hovered = img;
  if (img && !st.selected.has(img)) setOutline(img, HOVER_OUTLINE);
}

function onClick(e: Event): void {
  const st = state;
  if (!st) return;
  const me = e as MouseEvent;
  if ((me.target as HTMLElement)?.closest?.(`#${BAR_ID}`)) {
    return; // let the action-bar buttons work normally
  }
  // Suppress the site's own handlers while selecting
  e.preventDefault();
  e.stopPropagation();
  e.stopImmediatePropagation();

  const img = imageAt(me);
  if (!img) return;
  if (st.selected.has(img)) {
    st.selected.delete(img);
    setOutline(img, img === st.hovered ? HOVER_OUTLINE : null);
  } else {
    st.selected.add(img);
    setOutline(img, SELECTED_OUTLINE);
  }
  refreshCount();
}

function onKeyDown(e: Event): void {
  if ((e as KeyboardEvent).key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    stopSelectionOverlay();
  }
}

function buildBar(): [HTMLDivElement, HTMLSpanElement] {
  const bar = document.createElement("div");
  bar.id = BAR_ID;
  bar.style.cssText = [
    "position:fixed", "top:12px", "left:50%", "transform:translateX(-50%)",
    `z-index:${Z_MAX}`, "background:#2c2f33", "color:#dcddde",
    "border:1px solid #4f545c", "border-radius:8px", "padding:10px 14px",
    "font:13px sans-serif", "display:flex", "align-items:center", "gap:10px",
    "box-shadow:0 4px 16px rgba(0,0,0,.5)",
  ].join(";");

  const count = document.createElement("span");
  count.textContent = "0 images selected";

  const mkBtn = (label: string, bg: string): HTMLButtonElement => {
    const b = document.createElement("button");
    b.textContent = label;
    b.style.cssText =
      `background:${bg};color:#fff;border:none;border-radius:4px;` +
      "padding:6px 12px;cursor:pointer;font:inherit";
    return b;
  };

  const downloadBtn = mkBtn("Download selected", "#5865f2");
  downloadBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    downloadSelection();
  });
  const cancelBtn = mkBtn("Cancel", "#4f545c");
  cancelBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    stopSelectionOverlay();
  });

  bar.append(count, downloadBtn, cancelBtn);
  return [bar, count];
}

function downloadSelection(): void {
  const st = state;
  if (!st) return;
  const urls: string[] = [];
  const seen = new Set<string>();
  for (const img of st.selected) {
    const url = bestImageUrl(img);
    if (url && !seen.has(url)) {
      seen.add(url);
      urls.push(url);
    }
  }
  if (urls.length > 0) {
    const msg: DownloadBatchMsg = {
      action: "download_batch",
      urls,
      pageUrl: window.location.href,
    };
    void api.runtime.sendMessage(msg);
  }
  stopSelectionOverlay();
}

/** Enter selection mode. No-op if already active. */
export function startSelectionOverlay(): void {
  if (state) return;
  const [bar, countEl] = buildBar();
  document.documentElement.appendChild(bar);

  state = {
    selected: new Set(),
    savedOutline: new Map(),
    hovered: null,
    bar,
    countEl,
    listeners: [],
  };

  const add = (
    type: string,
    fn: EventListener,
    opts: boolean | AddEventListenerOptions,
  ) => {
    document.addEventListener(type, fn, opts);
    state?.listeners.push([type, fn, opts]);
  };
  add("mousemove", onMouseMove, true);
  add("click", onClick, { capture: true, passive: false });
  add("keydown", onKeyDown, true);
}

/** Leave selection mode, restoring all touched styles and listeners. */
export function stopSelectionOverlay(): void {
  const st = state;
  if (!st) return;
  state = null;
  for (const [type, fn, opts] of st.listeners) {
    document.removeEventListener(type, fn, opts);
  }
  for (const [img, outline] of st.savedOutline) {
    img.style.outline = outline;
    img.style.outlineOffset = "";
  }
  st.bar.remove();
}
