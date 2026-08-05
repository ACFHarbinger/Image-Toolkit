/**
 * Video clip capture → WebM / animated WebP (§7.15D) — content-script side.
 *
 * Companion to §7.15A's single-frame/burst capture in `videoCapture.ts`,
 * reusing its target-video resolution (`findVideo`) and naming
 * (`videoBaseName`) helpers rather than duplicating them.
 *
 * Two export formats, both entirely browser-native (no new dependency):
 *   - "webm": continuously draws the video onto an off-DOM canvas via
 *     `requestAnimationFrame`, feeds `canvas.captureStream()` into a
 *     `MediaRecorder`, and downloads the resulting WebM blob. This is the
 *     roadmap's literal MVP ("`MediaRecorder`-based clip capture → WebM").
 *   - "webp": samples the same draw loop at a fixed frame rate, encodes each
 *     sampled frame independently via `canvas.toBlob("image/webp")`, and
 *     muxes them into one animated WebP with `shared/webpMux.ts`. See that
 *     module's docstring for why WebP (not GIF) is the second format.
 *
 * Duration is a fixed constant (`CLIP_DURATION_SEC`), the same simplicity
 * §7.15A's burst count (fixed at 5) already established for this codebase —
 * a duration/quality picker panel is a natural follow-on, not attempted here
 * to keep this change bounded.
 */
import { api } from "./shared/api";
import { findVideo, videoBaseName, sleep } from "./videoCapture";
import { muxAnimatedWebp, type WebpFrame } from "./shared/webpMux";
import type { CaptureVideoClipMsg, CaptureVideoClipResponse, DownloadImageMsg } from "./shared/messages";

/** Sampling rate for both the WebM canvas stream and the WebP frame grabs. */
const CAPTURE_FPS = 10;

function pickWebmMimeType(): string {
  const candidates = [
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ];
  for (const type of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "video/webm";
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error ?? new Error("FileReader failed"));
    reader.readAsDataURL(blob);
  });
}

/** Draw `video` onto `canvas` continuously via rAF until `stop()` is called. */
function startDrawLoop(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
): { stop: () => void } {
  const ctx = canvas.getContext("2d");
  let raf = 0;
  const tick = (): void => {
    if (ctx) ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return { stop: () => cancelAnimationFrame(raf) };
}

async function recordWebm(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  durationSec: number,
): Promise<Blob> {
  const loop = startDrawLoop(video, canvas);
  try {
    const stream = canvas.captureStream(30);
    const recorder = new MediaRecorder(stream, { mimeType: pickWebmMimeType() });
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
    });
    recorder.start();
    await sleep(durationSec * 1000);
    recorder.stop();
    await stopped;
    return new Blob(chunks, { type: recorder.mimeType || "video/webm" });
  } finally {
    loop.stop();
  }
}

function canvasToWebpBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("toBlob returned null"))),
      "image/webp",
      0.85,
    );
  });
}

async function recordWebp(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  durationSec: number,
): Promise<Blob> {
  const loop = startDrawLoop(video, canvas);
  const intervalMs = 1000 / CAPTURE_FPS;
  const frameCount = Math.max(1, Math.round((durationSec * 1000) / intervalMs));
  const frames: WebpFrame[] = [];
  try {
    // Let the first frame settle before sampling.
    await sleep(intervalMs);
    for (let i = 0; i < frameCount; i++) {
      const blob = await canvasToWebpBlob(canvas);
      if (blob.type !== "image/webp") {
        throw new Error(
          "This browser's <canvas> cannot encode WebP — try Chrome, Edge, or Brave.",
        );
      }
      frames.push({ bytes: await blob.arrayBuffer(), durationMs: intervalMs });
      if (i < frameCount - 1) await sleep(intervalMs);
    }
  } finally {
    loop.stop();
  }
  return muxAnimatedWebp(frames, canvas.width, canvas.height, 0);
}

export async function captureVideoClip(
  msg: CaptureVideoClipMsg,
): Promise<CaptureVideoClipResponse> {
  const video = findVideo(msg.srcUrl);
  if (!video) return { ok: false, error: "No video found on this page." };
  if (!video.videoWidth || !video.videoHeight) {
    return { ok: false, error: "Video has no decodable frame yet." };
  }

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const base = videoBaseName(video);
  const stamp = Date.now();

  try {
    let blob: Blob;
    let ext: string;
    if (msg.format === "webm") {
      blob = await recordWebm(video, canvas, msg.durationSec);
      ext = "webm";
    } else {
      blob = await recordWebp(video, canvas, msg.durationSec);
      ext = "webp";
    }
    const dataUrl = await blobToDataUrl(blob);
    const dl: DownloadImageMsg = {
      action: "download_image",
      src: dataUrl,
      pageUrl: window.location.href,
      suggestedName: `${base}_clip_${stamp}.${ext}`,
    };
    void api.runtime.sendMessage(dl);
    return { ok: true };
  } catch (err) {
    const security = err instanceof DOMException && err.name === "SecurityError";
    return {
      ok: false,
      error: security
        ? "Video is cross-origin protected (CORS/DRM) — clip capture blocked by the browser."
        : String(err),
    };
  }
}
