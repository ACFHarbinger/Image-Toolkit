/**
 * GIF/APNG/animated-WebP frame extractor — grid-preview page (§7.15B).
 *
 * Opened by `background.ts`'s "Extract frames…" context-menu handler, which
 * stashes `{ imageUrl, pageUrl }` under `framesData` in storage.local (a new
 * tab can't receive constructor arguments directly — same hand-off pattern
 * as #102's `galleryData` → `gallery.ts`). This page fetches the image
 * itself, decodes it, and renders the frames as a grid with a large
 * scrubbable preview, mirroring `gallery.ts`'s established "detected items →
 * grid → per-item action" shape.
 *
 * Decoding: exclusively the WebCodecs `ImageDecoder` API (Chromium-based
 * browsers only). The roadmap's original plan listed `omggif`/`upng` as a
 * fallback for browsers without it; that fallback is deliberately not
 * bundled here — per this session's dependency-light bias, and because every
 * one of this extension's *build targets that matter for this feature*
 * (chrome/edge/brave) already ship `ImageDecoder`, while Firefox (the one
 * target that doesn't) gets a clear "not supported in this browser" message
 * instead of a corrupt/partial decode. If Firefox coverage becomes a
 * priority, adding `omggif`/`upng` as an explicit fallback path is a
 * contained follow-up — the grid/scrubber UI below is decoder-agnostic.
 */
import { api, storageGet } from "../shared/api";
import type { DownloadImageMsg, FramesData } from "../shared/messages";

const $ = <T extends HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

interface Frame {
  index: number;
  dataUrl: string;
  durationMs: number;
  selected: boolean;
  cell: HTMLDivElement;
  checkbox: HTMLInputElement;
}

let frames: Frame[] = [];
let imageUrl = "";
let baseName = "frame";
let playing = false;
let playTimer = 0;

function stemOf(url: string): string {
  try {
    const stem = new URL(url).pathname.split("/").pop()?.replace(/\.[a-z0-9]+$/i, "");
    if (stem) return stem;
  } catch {
    /* data: URLs etc. */
  }
  return "frame";
}

/** Sniff the animation container format from magic bytes — more reliable
 * than trusting a server's `Content-Type` header, which is frequently wrong
 * or absent for hotlinked/CDN images. */
function detectMime(bytes: Uint8Array): string | null {
  if (bytes.length >= 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
    return "image/gif"; // "GIF8..."
  }
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return "image/png"; // also covers APNG — same PNG signature
  }
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return "image/webp";
  }
  return null;
}

function showError(message: string): void {
  const el = $<HTMLDivElement>("empty");
  el.style.display = "block";
  el.textContent = message;
}

function frameToCanvasDataUrl(image: VideoFrame): string {
  const canvas = document.createElement("canvas");
  canvas.width = image.displayWidth;
  canvas.height = image.displayHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas context unavailable.");
  ctx.drawImage(image, 0, 0);
  return canvas.toDataURL("image/png");
}

async function decodeFrames(bytes: Uint8Array, mime: string): Promise<void> {
  if (typeof ImageDecoder === "undefined") {
    showError(
      "This browser doesn't support the WebCodecs ImageDecoder API needed to " +
        "extract frames — try Chrome, Edge, or Brave.",
    );
    return;
  }
  const supported = await ImageDecoder.isTypeSupported(mime).catch(() => false);
  if (!supported) {
    showError(`This browser's ImageDecoder can't decode ${mime}.`);
    return;
  }

  const decoder = new ImageDecoder({ data: bytes, type: mime, preferAnimation: true });
  await decoder.tracks.ready;
  const track = decoder.tracks.selectedTrack;
  const frameCount = track?.frameCount ?? 1;

  if (frameCount <= 1) {
    $<HTMLDivElement>("summary").textContent =
      "This image has only one frame (not animated) — showing it anyway.";
  }

  const grid = $<HTMLDivElement>("grid");
  grid.replaceChildren();
  frames = [];

  for (let i = 0; i < frameCount; i++) {
    const result = await decoder.decode({ frameIndex: i });
    const dataUrl = frameToCanvasDataUrl(result.image);
    const durationMs = result.image.duration ? result.image.duration / 1000 : 100;
    result.image.close();
    frames.push(buildCell(i, dataUrl, durationMs));
  }
  decoder.close();

  for (const f of frames) grid.appendChild(f.cell);
  if (frames.length > 0) {
    setPreview(0);
    $<HTMLInputElement>("scrubber").max = String(frames.length - 1);
    $<HTMLInputElement>("scrubber").disabled = frames.length <= 1;
    $<HTMLButtonElement>("play-pause").disabled = frames.length <= 1;
  }
  renderSummary();
}

function buildCell(index: number, dataUrl: string, durationMs: number): Frame {
  const cell = document.createElement("div");
  cell.className = "cell";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "cell-select";
  checkbox.checked = true;

  const thumbWrap = document.createElement("div");
  thumbWrap.className = "thumb-wrap";
  const img = document.createElement("img");
  img.src = dataUrl;
  img.alt = `Frame ${index + 1}`;
  thumbWrap.append(img, checkbox);
  thumbWrap.addEventListener("click", (e) => {
    if (e.target === checkbox) return;
    setPreview(index);
  });

  const meta = document.createElement("div");
  meta.className = "cell-meta";
  meta.innerHTML = `<span>#${index + 1}</span><span>${Math.round(durationMs)}ms</span>`;

  const actions = document.createElement("div");
  actions.className = "cell-actions";
  const downloadBtn = document.createElement("button");
  downloadBtn.textContent = "Save";
  actions.appendChild(downloadBtn);

  cell.append(thumbWrap, meta, actions);

  const f: Frame = { index, dataUrl, durationMs, selected: true, cell, checkbox };
  checkbox.addEventListener("change", () => {
    f.selected = checkbox.checked;
    renderSummary();
  });
  downloadBtn.addEventListener("click", () => downloadFrame(f));

  return f;
}

function setPreview(index: number): void {
  const f = frames[index];
  if (!f) return;
  $<HTMLImageElement>("preview-img").src = f.dataUrl;
  $<HTMLDivElement>("preview-label").textContent = `Frame ${index + 1} of ${frames.length}`;
  $<HTMLInputElement>("scrubber").value = String(index);
}

function togglePlay(): void {
  playing = !playing;
  $<HTMLButtonElement>("play-pause").textContent = playing ? "Pause" : "Play";
  if (playing) schedulePlayTick(Number($<HTMLInputElement>("scrubber").value));
  else window.clearTimeout(playTimer);
}

function schedulePlayTick(from: number): void {
  if (!playing || frames.length === 0) return;
  const next = (from + 1) % frames.length;
  setPreview(next);
  const delay = Math.max(20, frames[from]?.durationMs ?? 100);
  playTimer = window.setTimeout(() => schedulePlayTick(next), delay);
}

function downloadFrame(f: Frame): void {
  const msg: DownloadImageMsg = {
    action: "download_image",
    src: f.dataUrl,
    pageUrl: imageUrl,
    suggestedName: `${baseName}_frame${String(f.index + 1).padStart(3, "0")}.png`,
  };
  void api.runtime.sendMessage(msg);
}

function downloadSelected(): void {
  const targets = frames.filter((f) => f.selected);
  for (const f of targets) downloadFrame(f);
  renderSummary(`Queued ${targets.length} frame(s) for download.`);
}

function renderSummary(extra?: string): void {
  const selected = frames.filter((f) => f.selected).length;
  const summary = $<HTMLDivElement>("summary");
  summary.textContent = extra ?? `${frames.length} frame(s) decoded · ${selected} selected`;
}

document.addEventListener("DOMContentLoaded", () => {
  void storageGet<{ framesData: FramesData }>("framesData").then(async ({ framesData }) => {
    if (!framesData) {
      showError('No image selected. Open this from an image\'s "Extract frames…" context menu item.');
      return;
    }
    imageUrl = framesData.imageUrl;
    baseName = stemOf(imageUrl);
    $<HTMLDivElement>("source-url").textContent = imageUrl;

    try {
      const resp = await fetch(imageUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const bytes = new Uint8Array(await resp.arrayBuffer());
      const mime = detectMime(bytes);
      if (!mime) {
        showError("Couldn't identify this as a GIF, PNG/APNG, or WebP image.");
        return;
      }
      await decodeFrames(bytes, mime);
    } catch (err) {
      showError(`Failed to load or decode this image: ${String(err)}`);
    }
  });

  $<HTMLInputElement>("scrubber").addEventListener("input", (e) => {
    setPreview(Number((e.target as HTMLInputElement).value));
  });
  $<HTMLButtonElement>("play-pause").addEventListener("click", togglePlay);
  $<HTMLButtonElement>("select-all").addEventListener("click", () => {
    for (const f of frames) {
      f.selected = true;
      f.checkbox.checked = true;
    }
    renderSummary();
  });
  $<HTMLButtonElement>("select-none").addEventListener("click", () => {
    for (const f of frames) {
      f.selected = false;
      f.checkbox.checked = false;
    }
    renderSummary();
  });
  $<HTMLButtonElement>("download-selected").addEventListener("click", downloadSelected);
});
