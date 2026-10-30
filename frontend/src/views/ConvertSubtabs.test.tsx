import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SamplerPanel } from "./ConvertSubtabs";

afterEach(() => {
  cleanup();
  vi.mocked(invoke).mockReset();
});

function resampleCalls() {
  return vi.mocked(invoke).mock.calls.filter((call) => {
    const args = call[1] as { action?: string } | undefined;
    return args?.action === "resample";
  });
}

const resampleParams = {
  mode: "factor",
  factor: 0.5,
  width: 1280,
  height: 720,
  algorithm: "lanczos",
};

test("resamples every selected still beside the source when output is empty", async () => {
  vi.mocked(invoke).mockResolvedValue({ success: true });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), {
    target: { value: "/pics/a.png\n/pics/b.jpg" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([
    ["media_subtab", {
      action: "resample",
      params: { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png", ...resampleParams, batch: [
        { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png" },
        { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg" },
      ] },
    }],
    ["media_subtab", {
      action: "resample",
      params: { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg", ...resampleParams, batch: [
        { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png" },
        { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg" },
      ] },
    }],
  ]);
});

test("one path uses the output field as the exact output path", async () => {
  vi.mocked(invoke).mockResolvedValue({ success: true });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out/custom.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([
    ["media_subtab", {
      action: "resample",
      params: { input_path: "/pics/a.png", output_path: "/out/custom.png", ...resampleParams, batch: [{ input_path: "/pics/a.png", output_path: "/out/custom.png" }] },
    }],
  ]);
});

test("an output directory that is the source directory does not replace the files", async () => {
  vi.mocked(invoke).mockResolvedValue({ success: true });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), {
    target: { value: "/pics/a.png\n/pics/b.jpg" },
  });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/pics" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: failed: refusing to replace a selected source")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([]);
});

test("empty input does not resample", () => {
  render(<SamplerPanel />);
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(resampleCalls()).toEqual([]);
  expect(screen.getByText("Status: error: input required")).toBeInTheDocument();
});

test("preflights every destination against every selected source", async () => {
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/in/a.png\n/out/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: failed: refusing to replace a selected source")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([]);
});

test("keeps a gif extension so each frame can be resized", async () => {
  vi.mocked(invoke).mockResolvedValue({ success: true });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/clip.gif" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([
    ["media_subtab", {
      action: "resample",
      params: {
        input_path: "/pics/clip.gif",
        output_path: "/pics/clip_resampled.gif",
        ...resampleParams,
        batch: [{ input_path: "/pics/clip.gif", output_path: "/pics/clip_resampled.gif" }],
      },
    }],
  ]);
});

test("rejects two inputs that would share one output", async () => {
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/in/a.png\n/other/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: failed: multiple inputs have the same output path")).toBeInTheDocument();
  expect(resampleCalls()).toEqual([]);
});

test("lists registry backends and disables an unavailable GIF algorithm", async () => {
  vi.mocked(invoke).mockImplementation(async (_command, args: { action?: string } | undefined) => {
    if (args?.action === "list_resample_algorithms") {
      return {
        success: true,
        algorithms: [
          { id: "lanczos", content: "any", kind: "classical", available: true, reason: "" },
          { id: "anime4k", content: "anime", kind: "classical", available: true, reason: "" },
          { id: "realesrgan-anime-6b", content: "anime", kind: "neural", available: false, reason: "weights are not cached" },
        ],
      };
    }
    return { success: true };
  });
  render(<SamplerPanel />);
  expect(await screen.findByRole("option", { name: "anime4k" })).toBeEnabled();
  expect(screen.getByRole("option", { name: "realesrgan-anime-6b (weights are not cached)" })).toBeDisabled();
});

test("hides a gif-only algorithm when the selection is a still or a mix", async () => {
  vi.mocked(invoke).mockImplementation(async (_command, args: { action?: string } | undefined) => {
    if (args?.action === "list_resample_algorithms") {
      return {
        success: true,
        algorithms: [
          { id: "lanczos", content: "any", kind: "classical", available: true, reason: "", containers: ["gif", "still"] },
          { id: "gif-palette", content: "any", kind: "classical", available: true, reason: "", containers: ["gif"] },
        ],
      };
    }
    return { success: true };
  });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/a.png" } });
  expect(await screen.findByRole("option", { name: "lanczos" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "gif-palette" })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/a.png\n/pics/clip.gif" } });
  expect(screen.queryByRole("option", { name: "gif-palette" })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/clip.gif" } });
  expect(await screen.findByRole("option", { name: "gif-palette" })).toBeInTheDocument();
});
