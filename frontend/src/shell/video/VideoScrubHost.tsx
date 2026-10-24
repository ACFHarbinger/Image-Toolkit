import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  createScrubController,
  formatTimecode,
  frameToTime,
  probeCodecSupport,
  resolveVideoAssetUrl,
  timeToFrame,
  VideoCodecSupportMatrix,
} from "./videoScrubber";

export interface VideoScrubHostProps {
  videoPath?: string;
  fps?: number;
  initialTotalFrames?: number;
  onFrameChange?: (frame: number) => void;
}

export function VideoScrubHost({
  videoPath = "/data/videos/sample_1080p.mp4",
  fps = 30,
  initialTotalFrames = 300,
  onFrameChange,
}: VideoScrubHostProps): React.ReactElement {
  const [currentFrame, setCurrentFrame] = useState(0);
  const [totalFrames, setTotalFrames] = useState(initialTotalFrames);
  const [isPlaying, setIsPlaying] = useState(false);
  const [codecs, setCodecs] = useState<VideoCodecSupportMatrix | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  const asset = useMemo(() => resolveVideoAssetUrl(videoPath), [videoPath]);

  useEffect(() => {
    setCodecs(probeCodecSupport());
  }, []);

  const scrubber = useMemo(() => {
    return createScrubController({
      fps,
      onSeek: (targetTimeSec) => {
        if (videoRef.current) {
          videoRef.current.currentTime = targetTimeSec;
        }
      },
    });
  }, [fps]);

  useEffect(() => {
    return () => {
      scrubber.cancel();
    };
  }, [scrubber]);

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const frame = timeToFrame(videoRef.current.currentTime, fps);
    setCurrentFrame(frame);
    onFrameChange?.(frame);
  };

  const handleSeeked = () => {
    scrubber.markSeekCompleted();
    if (videoRef.current) {
      const frame = timeToFrame(videoRef.current.currentTime, fps);
      setCurrentFrame(frame);
      onFrameChange?.(frame);
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    const durationSec = videoRef.current.duration;
    if (durationSec && !Number.isNaN(durationSec)) {
      setTotalFrames(Math.max(1, Math.round(durationSec * fps)));
    }
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const frame = parseInt(e.target.value, 10);
    setCurrentFrame(frame);
    scrubber.scrubToFrame(frame);
    onFrameChange?.(frame);
  };

  const stepFrame = (delta: number) => {
    const next = Math.max(0, Math.min(totalFrames - 1, currentFrame + delta));
    setCurrentFrame(next);
    scrubber.scrubToFrame(next);
    onFrameChange?.(next);
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      void videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  return (
    <div
      data-testid="video-scrub-host"
      className="flex h-full w-full flex-col rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      {/* Top Header & Codec Support Bar */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-800 dark:bg-gray-900/60">
        <div className="flex items-center gap-3">
          <span className="text-base">🎬</span>
          <div>
            <span className="text-xs font-bold text-gray-800 dark:text-gray-200">
              Video Player & Accurate Frame Scrubber
            </span>
            <div className="text-[10px] text-gray-500 font-mono truncate max-w-sm">
              {videoPath}
            </div>
          </div>
        </div>

        {codecs && (
          <div data-testid="codec-support-matrix" className="flex items-center gap-1.5 text-[10px]">
            <span className="text-gray-400">Codecs:</span>
            <span
              data-testid="codec-h264"
              className={`rounded px-1.5 py-0.5 font-mono ${
                codecs.h264 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" : "bg-gray-100 text-gray-400"
              }`}
            >
              H.264 {codecs.h264 ? "✓" : "✗"}
            </span>
            <span
              data-testid="codec-vp9"
              className={`rounded px-1.5 py-0.5 font-mono ${
                codecs.vp9 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" : "bg-gray-100 text-gray-400"
              }`}
            >
              VP9 {codecs.vp9 ? "✓" : "✗"}
            </span>
            <span
              data-testid="codec-av1"
              className={`rounded px-1.5 py-0.5 font-mono ${
                codecs.av1 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" : "bg-gray-100 text-gray-400"
              }`}
            >
              AV1 {codecs.av1 ? "✓" : "✗"}
            </span>
            <span
              data-testid="codec-hevc"
              className={`rounded px-1.5 py-0.5 font-mono ${
                codecs.hevc ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" : "bg-gray-100 text-gray-400"
              }`}
            >
              HEVC {codecs.hevc ? "✓" : "✗"}
            </span>
          </div>
        )}
      </header>

      {/* Main Video Viewport */}
      <div className="relative flex flex-1 items-center justify-center bg-black overflow-hidden min-h-[240px]">
        {!asset.valid ? (
          <div data-testid="video-error-banner" className="text-center p-6 text-red-400 text-xs">
            <span className="text-2xl">⚠</span>
            <p className="mt-1 font-semibold">{asset.error}</p>
          </div>
        ) : (
          <video
            ref={videoRef}
            data-testid="video-element"
            src={asset.assetUrl}
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleSeeked}
            onLoadedMetadata={handleLoadedMetadata}
            className="max-h-full max-w-full"
            playsInline
          />
        )}
      </div>

      {/* Frame Scrubber & Playback Controls */}
      <footer className="border-t border-gray-200 bg-gray-50 p-4 space-y-3 dark:border-gray-800 dark:bg-gray-900/60">
        {/* Scrubber Slider */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span data-testid="current-timecode" className="font-bold text-indigo-600 dark:text-indigo-400">
              {formatTimecode(currentFrame, fps)}
            </span>
            <span data-testid="frame-counter" className="text-gray-500 dark:text-gray-400">
              Frame {currentFrame} / {totalFrames} ({fps} fps)
            </span>
          </div>

          <input
            type="range"
            data-testid="frame-scrubber-slider"
            min={0}
            max={Math.max(1, totalFrames - 1)}
            value={currentFrame}
            onChange={handleSliderChange}
            className="w-full accent-indigo-600 cursor-pointer"
          />
        </div>

        {/* Transport Actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="btn-step-prev"
              onClick={() => stepFrame(-1)}
              className="rounded border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800"
              title="Step backward 1 frame"
            >
              -1f
            </button>
            <button
              type="button"
              data-testid="btn-play-pause"
              onClick={togglePlay}
              className="rounded bg-indigo-600 px-4 py-1 text-xs font-bold text-white shadow hover:bg-indigo-700"
            >
              {isPlaying ? "Pause ❚❚" : "Play ▶"}
            </button>
            <button
              type="button"
              data-testid="btn-step-next"
              onClick={() => stepFrame(1)}
              className="rounded border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800"
              title="Step forward 1 frame"
            >
              +1f
            </button>
          </div>

          <div className="flex items-center gap-2 text-[10px] text-gray-500">
            <span className="rounded bg-gray-200 px-2 py-0.5 dark:bg-gray-800 font-mono">
              HTTP 206 Partial Content (Byte Ranges)
            </span>
            <span>Target: {frameToTime(currentFrame, fps).toFixed(3)}s</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
