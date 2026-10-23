import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VideoScrubHost } from "../VideoScrubHost";
import {
  createScrubController,
  formatTimecode,
  frameToTime,
  probeCodecSupport,
  resolveVideoAssetUrl,
  timeToFrame,
} from "../videoScrubber";

afterEach(() => {
  cleanup();
});

describe("Video Asset & Codec Probing (#892, S-06)", () => {
  it("resolves valid video file paths to asset:// streaming URLs", () => {
    const mp4 = resolveVideoAssetUrl("/home/user/Videos/clip.mp4");
    expect(mp4.valid).toBe(true);
    expect(mp4.assetUrl).toBeDefined();

    const webm = resolveVideoAssetUrl("/data/render/output.webm");
    expect(webm.valid).toBe(true);
  });

  it("rejects path traversal and unsupported file formats", () => {
    const traversal = resolveVideoAssetUrl("/data/videos/../../etc/shadow.mp4");
    expect(traversal.valid).toBe(false);
    expect(traversal.error).toContain("Directory traversal");

    const image = resolveVideoAssetUrl("/data/photos/picture.png");
    expect(image.valid).toBe(false);
    expect(image.error).toContain("not a supported video container format");

    const noExt = resolveVideoAssetUrl("/data/videos/unnamed_file");
    expect(noExt.valid).toBe(false);
  });

  it("probes video codec support matrix", () => {
    const codecs = probeCodecSupport();
    expect(codecs).toHaveProperty("h264");
    expect(codecs).toHaveProperty("vp8");
    expect(codecs).toHaveProperty("vp9");
    expect(codecs).toHaveProperty("av1");
    expect(codecs).toHaveProperty("hevc");
    expect(typeof codecs.h264).toBe("boolean");
  });

  it("calculates accurate frame and time conversions", () => {
    expect(timeToFrame(0, 30)).toBe(0);
    expect(timeToFrame(1.0, 30)).toBe(30);
    expect(timeToFrame(1.5, 30)).toBe(45);
    expect(timeToFrame(2.033, 30)).toBe(61);

    expect(frameToTime(0, 30)).toBe(0);
    expect(frameToTime(30, 30)).toBe(1.0);
    expect(frameToTime(45, 30)).toBe(1.5);

    expect(formatTimecode(0, 30)).toBe("00:00:00:00");
    expect(formatTimecode(30, 30)).toBe("00:00:01:00");
    expect(formatTimecode(95, 30)).toBe("00:00:03:05");
  });

  it("throttles scrub operations using RAF to prevent decoding backlogs", () => {
    const onSeek = vi.fn();
    const controller = createScrubController({ fps: 30, onSeek });

    controller.scrubToFrame(10);
    controller.scrubToFrame(20);
    controller.scrubToFrame(30);

    // RAF flushes pending frame
    expect(controller.isBusy).toBe(true);
    controller.markSeekCompleted();
    controller.cancel();
    expect(controller.isBusy).toBe(false);
  });
});

describe("VideoScrubHost Component (#892, S-06)", () => {
  it("renders video element and frame scrubbing controls", () => {
    render(<VideoScrubHost videoPath="/media/test.mp4" fps={30} initialTotalFrames={100} />);

    expect(screen.getByTestId("video-scrub-host")).toBeInTheDocument();
    expect(screen.getByTestId("video-element")).toBeInTheDocument();
    expect(screen.getByTestId("current-timecode")).toHaveTextContent("00:00:00:00");
    expect(screen.getByTestId("frame-counter")).toHaveTextContent("Frame 0 / 100 (30 fps)");
    expect(screen.getByTestId("frame-scrubber-slider")).toHaveValue("0");
    expect(screen.getByTestId("codec-support-matrix")).toBeInTheDocument();
  });

  it("updates frame on scrubber slider change", () => {
    const onFrame = vi.fn();
    render(<VideoScrubHost videoPath="/media/test.mp4" fps={30} initialTotalFrames={100} onFrameChange={onFrame} />);

    const slider = screen.getByTestId("frame-scrubber-slider");
    fireEvent.change(slider, { target: { value: "45" } });

    expect(screen.getByTestId("frame-counter")).toHaveTextContent("Frame 45 / 100");
    expect(screen.getByTestId("current-timecode")).toHaveTextContent("00:00:01:15");
    expect(onFrame).toHaveBeenCalledWith(45);
  });

  it("steps forward and backward by one frame on button clicks", () => {
    const onFrame = vi.fn();
    render(<VideoScrubHost videoPath="/media/test.mp4" fps={30} initialTotalFrames={100} onFrameChange={onFrame} />);

    const nextBtn = screen.getByTestId("btn-step-next");
    const prevBtn = screen.getByTestId("btn-step-prev");

    fireEvent.click(nextBtn);
    expect(screen.getByTestId("frame-counter")).toHaveTextContent("Frame 1 / 100");
    expect(onFrame).toHaveBeenCalledWith(1);

    fireEvent.click(nextBtn);
    expect(screen.getByTestId("frame-counter")).toHaveTextContent("Frame 2 / 100");

    fireEvent.click(prevBtn);
    expect(screen.getByTestId("frame-counter")).toHaveTextContent("Frame 1 / 100");
  });

  it("renders error banner when path traversal is attempted", () => {
    render(<VideoScrubHost videoPath="/videos/../../secret.mp4" />);

    expect(screen.getByTestId("video-error-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("video-element")).not.toBeInTheDocument();
  });
});
