/**
 * Video frame capture (§7.15A) — content-script side.
 *
 * Captures the current frame of a <video> at its native resolution
 * (videoWidth × videoHeight) onto a canvas and hands the PNG to the
 * background downloader. Burst mode grabs N frames at a fixed interval from
 * the live video. Cross-origin video without CORS headers taints the canvas;
 * that surfaces as a clear error instead of a corrupt file.
 */
import { api } from "./shared/api";
import type {
  CaptureVideoFrameMsg,
  CaptureVideoFrameResponse,
  DownloadImageMsg,
} from "./shared/messages";

/** Last element the user opened a context menu on (set by content.ts). */
let lastContextTarget: Element | null = null;

export function rememberContextTarget(el: Element | null): void {
  lastContextTarget = el;
}

function findVideo(srcUrl?: string): HTMLVideoElement | null {
  if (lastContextTarget instanceof HTMLVideoElement) return lastContextTarget;
  const videos = [...document.querySelectorAll<HTMLVideoElement>("video")];
  if (srcUrl) {
    const match = videos.find(
      (v) =>
        v.currentSrc === srcUrl ||
        v.src === srcUrl ||
        [...v.querySelectorAll("source")].some((s) => s.src === srcUrl),
    );
    if (match) return match;
  }
  return videos[0] ?? null;
}

function videoBaseName(video: HTMLVideoElement): string {
  try {
    const stem = new URL(video.currentSrc || video.src, document.baseURI)
      .pathname.split("/").pop()?.replace(/\.[a-z0-9]+$/i, "");
    if (stem) return stem;
  } catch {
    /* blob:/MSE sources */
  }
  return "video";
}

function grabFrame(video: HTMLVideoElement): string {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx || canvas.width === 0) {
    throw new Error("Video has no decodable frame yet.");
  }
  ctx.drawImage(video, 0, 0);
  // Throws SecurityError on tainted (cross-origin / DRM) canvases
  return canvas.toDataURL("image/png");
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function captureVideoFrames(
  msg: CaptureVideoFrameMsg,
): Promise<CaptureVideoFrameResponse> {
  const video = findVideo(msg.srcUrl);
  if (!video) return { ok: false, error: "No video found on this page." };

  const base = videoBaseName(video);
  const stamp = Date.now();
  const count = Math.max(1, msg.burst);

  for (let i = 0; i < count; i++) {
    let dataUrl: string;
    try {
      dataUrl = grabFrame(video);
    } catch (err) {
      const security =
        err instanceof DOMException && err.name === "SecurityError";
      return {
        ok: i > 0, // partial burst still counts as success
        frames: i,
        error: security
          ? "Video is cross-origin protected (CORS/DRM) — frame capture blocked by the browser."
          : String(err),
      };
    }
    const suffix =
      count > 1 ? `_f${String(i + 1).padStart(2, "0")}` : "";
    const dl: DownloadImageMsg = {
      action: "download_image",
      src: dataUrl,
      pageUrl: window.location.href,
      suggestedName: `${base}_${stamp}${suffix}.png`,
    };
    void api.runtime.sendMessage(dl);
    if (i < count - 1) await sleep(msg.intervalMs);
  }
  return { ok: true, frames: count };
}
