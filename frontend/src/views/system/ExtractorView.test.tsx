import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ExtractorView } from "./ExtractorView";

afterEach(() => {
  cleanup();
});

test("probe shows the returned stream", async () => {
  const hostClient = {
    extractorProbe: vi.fn().mockResolvedValue({
      available: true,
      width: 320,
      height: 240,
      duration_seconds: 1.5,
      codec: "h264",
      error: "",
    }),
    extractorSnapshot: vi.fn(),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn(),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Video"), { target: { value: "/clip.mp4" } });
  fireEvent.click(screen.getByRole("button", { name: "Probe" }));
  expect(await screen.findByText("320x240 h264 1.5s")).toBeInTheDocument();
  expect(hostClient.extractorProbe).toHaveBeenCalledWith({ path: "/clip.mp4" });
});

test("cut sheet sends offset, spacing, and partial frames", async () => {
  const hostClient = {
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn().mockResolvedValue({ written: true, output_path: "/frame.png", error: "" }),
    extractorExtractRange: vi.fn().mockResolvedValue({ written: true, output_path: "/range.mp4", error: "" }),
    extractorCutSheet: vi.fn().mockResolvedValue({
      written: true,
      output_dir: "/frames",
      width: 10,
      height: 4,
      paths: ["/frames/frame_001.png"],
      error: "",
    }),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Video"), { target: { value: "/clip.mp4" } });
  fireEvent.change(screen.getByLabelText("Snapshot output"), { target: { value: "/frame.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Snapshot" }));
  expect(await screen.findByText("/frame.png")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Range output"), { target: { value: "/range.mp4" } });
  fireEvent.click(screen.getByRole("button", { name: "Extract range" }));
  expect(await screen.findByText("/range.mp4")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Sheet image"), { target: { value: "/sheet.png" } });
  fireEvent.change(screen.getByLabelText("Sheet output"), { target: { value: "/frames" } });
  fireEvent.change(screen.getByLabelText("Offset x"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Spacing"), { target: { value: "2" } });
  fireEvent.click(screen.getByLabelText("Include partial last frame"));
  fireEvent.click(screen.getByRole("button", { name: "Cut sheet" }));
  expect(await screen.findByText("10x4 1")).toBeInTheDocument();
  expect(hostClient.extractorSnapshot).toHaveBeenCalledWith({
    path: "/clip.mp4",
    time_seconds: 0,
    output_path: "/frame.png",
  });
  expect(hostClient.extractorExtractRange).toHaveBeenCalledWith({
    path: "/clip.mp4",
    start_seconds: 0,
    end_seconds: 1,
    output_path: "/range.mp4",
  });
  expect(hostClient.extractorCutSheet).toHaveBeenCalledWith({
    path: "/sheet.png",
    output_dir: "/frames",
    arrangement: "grid",
    frame_width: 32,
    frame_height: 32,
    offset_x: 1,
    offset_y: 0,
    spacing: 2,
    include_partial: true,
  });
});
