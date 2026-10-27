import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ExtractorView } from "./ExtractorView";

afterEach(() => {
  cleanup();
});

test("probe shows the returned stream", async () => {
  const hostClient = {
    cancelJob: vi.fn(),
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
    jobStatus: vi.fn(),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Video"), { target: { value: "/clip.mp4" } });
  fireEvent.click(screen.getByRole("button", { name: "Probe" }));
  expect(await screen.findByText("320x240 h264 1.5s")).toBeInTheDocument();
  expect(hostClient.extractorProbe).toHaveBeenCalledWith({ path: "/clip.mp4" });
});

test("cut sheet sends offset, spacing, and partial frames", async () => {
  const hostClient = {
    cancelJob: vi.fn(),
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    extractorExtractRange: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    jobStatus: vi
      .fn()
      .mockResolvedValueOnce({
        state: "completed",
        result: { written: true, output_path: "/frame.png", error: "" },
      })
      .mockResolvedValueOnce({
        state: "completed",
        result: { written: true, output_path: "/range.mp4", error: "" },
      })
      .mockResolvedValueOnce({
        state: "completed",
        result: {
          written: true,
          output_dir: "/frames",
          width: 10,
          height: 4,
          paths: ["/frames/frame_001.png"],
          error: "",
        },
      }),
    extractorCutSheet: vi.fn().mockResolvedValue({ job_id: "cut-1" }),
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

test("sheet job can be cancelled while the worker is running", async () => {
  let cancelled = false;
  const hostClient = {
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn(),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn().mockResolvedValue({ job_id: "cut-job" }),
    jobStatus: vi.fn().mockImplementation(async () => ({ state: cancelled ? "cancelled" : "running" })),
    cancelJob: vi.fn().mockImplementation(async () => { cancelled = true; }),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.click(screen.getByRole("button", { name: "Cut sheet" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel sheet cut" }));
  expect(await screen.findByText("cancelled")).toBeInTheDocument();
  expect(hostClient.cancelJob).toHaveBeenCalledWith("cut-job");
});

test("snapshot job can be cancelled while the worker is running", async () => {
  let cancelled = false;
  const hostClient = {
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn().mockResolvedValue({ job_id: "snap-job" }),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn(),
    jobStatus: vi.fn().mockImplementation(async () => ({ state: cancelled ? "cancelled" : "running" })),
    cancelJob: vi.fn().mockImplementation(async () => { cancelled = true; }),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.click(screen.getByRole("button", { name: "Snapshot" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(await screen.findByText("cancelled")).toBeInTheDocument();
  expect(hostClient.cancelJob).toHaveBeenCalledWith("snap-job");
});

test("a scanned sheet thumbnail fills the sheet image and does not start a job", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/sheets/grid.png"];
    }
    return {};
  });
  const hostClient = {
    cancelJob: vi.fn(),
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn(),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn(),
    jobStatus: vi.fn(),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Sheet directory"), { target: { value: "/sheets" } });
  const scans = screen.getAllByRole("button", { name: "Scan" });
  fireEvent.click(scans[scans.length - 1]);
  fireEvent.click(await screen.findByRole("option", { name: "grid.png" }));
  expect(screen.getByLabelText("Sheet image")).toHaveValue("/sheets/grid.png");
  expect(hostClient.extractorCutSheet).not.toHaveBeenCalled();
  expect(hostClient.extractorSnapshot).not.toHaveBeenCalled();
  expect(hostClient.extractorExtractRange).not.toHaveBeenCalled();
  vi.mocked(invoke).mockReset();
});

test("a scanned video thumbnail fills the video path and does not start a job", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/clips/clip.mp4"];
    }
    return {};
  });
  const hostClient = {
    cancelJob: vi.fn(),
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn(),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn(),
    jobStatus: vi.fn(),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Video directory"), { target: { value: "/clips" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Scan" })[0]);
  fireEvent.click(await screen.findByRole("option", { name: "clip.mp4" }));
  expect(screen.getByLabelText("Video")).toHaveValue("/clips/clip.mp4");
  expect(screen.getByLabelText("Sheet image")).toHaveValue("");
  expect(hostClient.extractorProbe).not.toHaveBeenCalled();
  expect(hostClient.extractorSnapshot).not.toHaveBeenCalled();
  expect(hostClient.extractorExtractRange).not.toHaveBeenCalled();
  expect(hostClient.extractorCutSheet).not.toHaveBeenCalled();
  expect(hostClient.cancelJob).not.toHaveBeenCalled();
  vi.mocked(invoke).mockReset();
});

test("browse output dialogs fill snapshot and sheet fields without starting a job", async () => {
  const hostClient = {
    cancelJob: vi.fn(),
    extractorProbe: vi.fn(),
    extractorSnapshot: vi.fn(),
    extractorExtractRange: vi.fn(),
    extractorCutSheet: vi.fn(),
    jobStatus: vi.fn(),
  };
  render(<ExtractorView hostClient={hostClient} />);
  vi.mocked(open).mockResolvedValueOnce("/frames/shot.png");
  fireEvent.click(screen.getByRole("button", { name: "Browse snapshot output" }));
  await waitFor(() => expect(screen.getByLabelText("Snapshot output")).toHaveValue("/frames/shot.png"));
  expect(open).toHaveBeenCalledWith({ directory: false, multiple: false });
  expect(hostClient.extractorProbe).not.toHaveBeenCalled();
  expect(hostClient.extractorSnapshot).not.toHaveBeenCalled();
  expect(hostClient.extractorExtractRange).not.toHaveBeenCalled();
  expect(hostClient.extractorCutSheet).not.toHaveBeenCalled();
  expect(hostClient.cancelJob).not.toHaveBeenCalled();
  vi.mocked(open).mockResolvedValueOnce("/frames");
  fireEvent.click(screen.getByRole("button", { name: "Browse sheet output" }));
  await waitFor(() => expect(screen.getByLabelText("Sheet output")).toHaveValue("/frames"));
  expect(open).toHaveBeenLastCalledWith({ directory: true, multiple: false });
  vi.mocked(open).mockReset();
  vi.mocked(open).mockImplementation(() => Promise.resolve(null));
});
