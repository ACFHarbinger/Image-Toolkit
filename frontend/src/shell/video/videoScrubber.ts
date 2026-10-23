/**
 * Video playback, asset streaming, and accurate frame scrubbing (#892, S-06).
 *
 * Implements scoped asset protocol resolution, codec support probing (H.264, VP9, AV1, HEVC),
 * exact time/frame conversions, and throttled scrubbing via requestAnimationFrame.
 */

import { convertFileSrc } from "@tauri-apps/api/core";

export const SUPPORTED_VIDEO_EXTENSIONS = new Set(["mp4", "webm", "mkv", "mov", "avi"]);

export interface VideoAssetResult {
  valid: boolean;
  assetUrl?: string;
  error?: string;
}

export interface VideoCodecSupportMatrix {
  h264: boolean;
  vp8: boolean;
  vp9: boolean;
  av1: boolean;
  hevc: boolean;
}

/**
 * Validates the local video path and converts it to a scoped asset:// streaming URL.
 * Traversal (..) and disallowed file extensions are rejected.
 */
export function resolveVideoAssetUrl(filePath: string): VideoAssetResult {
  if (!filePath || typeof filePath !== "string") {
    return { valid: false, error: "Video path is required." };
  }

  const clean = filePath.trim();
  if (clean.includes("..") || clean.includes("\0")) {
    return { valid: false, error: "Directory traversal (..) or null characters are rejected." };
  }

  const dotIdx = clean.lastIndexOf(".");
  if (dotIdx === -1) {
    return { valid: false, error: "Video path lacks a valid file extension." };
  }

  const ext = clean.slice(dotIdx + 1).toLowerCase();
  if (!SUPPORTED_VIDEO_EXTENSIONS.has(ext)) {
    return {
      valid: false,
      error: `Extension '.${ext}' is not a supported video container format.`,
    };
  }

  try {
    const assetUrl = convertFileSrc(clean);
    return { valid: true, assetUrl };
  } catch (err: unknown) {
    return {
      valid: false,
      error: `Failed to resolve asset protocol URL: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}

/**
 * Probes browser engine capabilities for HTML5 video codecs.
 */
export function probeCodecSupport(): VideoCodecSupportMatrix {
  if (typeof document === "undefined") {
    return { h264: true, vp8: true, vp9: true, av1: false, hevc: false };
  }

  const video = document.createElement("video");
  const canPlay = (mime: string): boolean => {
    try {
      const res = video.canPlayType(mime);
      return res === "probably" || res === "maybe";
    } catch {
      return false;
    }
  };

  return {
    h264: canPlay('video/mp4; codecs="avc1.42E01E"') || canPlay('video/mp4; codecs="avc1.64001F"'),
    vp8: canPlay('video/webm; codecs="vp8"'),
    vp9: canPlay('video/webm; codecs="vp9"'),
    av1: canPlay('video/mp4; codecs="av01.0.08M.08"'),
    hevc: canPlay('video/mp4; codecs="hvc1.1.6.L93.B0"') || canPlay('video/mp4; codecs="hev1.1.6.L93.B0"'),
  };
}

/**
 * Converts a floating-point playback time in seconds to the nearest discrete integer frame index.
 */
export function timeToFrame(timeSec: number, fps: number): number {
  if (timeSec <= 0 || fps <= 0) return 0;
  return Math.round(timeSec * fps);
}

/**
 * Converts an integer frame index to playback time in seconds.
 */
export function frameToTime(frameIndex: number, fps: number): number {
  if (frameIndex <= 0 || fps <= 0) return 0;
  return frameIndex / fps;
}

/**
 * Formats a frame number and time into standard SMPTE timecode (HH:MM:SS:FF).
 */
export function formatTimecode(frameIndex: number, fps: number): string {
  const safeFps = Math.max(1, fps);
  const totalSeconds = Math.floor(frameIndex / safeFps);
  const frameRem = Math.floor(frameIndex % safeFps);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}:${pad(frameRem)}`;
}

export interface ScrubControllerOptions {
  fps: number;
  onSeek: (timeSec: number) => void;
}

/**
 * Creates an accurate, throttled scrubber controller latching rapid seek requests
 * to requestAnimationFrame, avoiding decoding backlogs during continuous slider drags.
 */
export function createScrubController(options: ScrubControllerOptions) {
  let pendingFrame: number | null = null;
  let rafId: number | null = null;
  let isSeeking = false;

  const flush = () => {
    rafId = null;
    if (pendingFrame === null) return;

    const frameToSeek = pendingFrame;
    pendingFrame = null;
    isSeeking = true;

    const targetTime = frameToTime(frameToSeek, options.fps);
    options.onSeek(targetTime);
  };

  return {
    scrubToFrame(frameIndex: number) {
      pendingFrame = frameIndex;
      if (rafId === null) {
        if (typeof requestAnimationFrame !== "undefined") {
          rafId = requestAnimationFrame(flush);
        } else {
          flush();
        }
      }
    },
    markSeekCompleted() {
      isSeeking = false;
      if (pendingFrame !== null && rafId === null) {
        if (typeof requestAnimationFrame !== "undefined") {
          rafId = requestAnimationFrame(flush);
        } else {
          flush();
        }
      }
    },
    cancel() {
      if (rafId !== null && typeof cancelAnimationFrame !== "undefined") {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      pendingFrame = null;
      isSeeking = false;
    },
    get isBusy() {
      return isSeeking || pendingFrame !== null;
    },
  };
}
