import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SamplerPanel } from "./ConvertSubtabs";

afterEach(() => {
  cleanup();
  vi.mocked(invoke).mockReset();
});

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
  expect(invoke).toHaveBeenCalledTimes(2);
  expect(invoke).toHaveBeenNthCalledWith(1, "media_subtab", {
    action: "resample",
    params: { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png", ...resampleParams, batch: [
      { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png" },
      { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg" },
    ] },
  });
  expect(invoke).toHaveBeenNthCalledWith(2, "media_subtab", {
    action: "resample",
    params: { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg", ...resampleParams, batch: [
      { input_path: "/pics/a.png", output_path: "/pics/a_resampled.png" },
      { input_path: "/pics/b.jpg", output_path: "/pics/b_resampled.jpg" },
    ] },
  });
});

test("one path uses the output field as the exact output path", async () => {
  vi.mocked(invoke).mockResolvedValue({ success: true });
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/pics/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out/custom.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  expect(invoke).toHaveBeenCalledTimes(1);
  expect(invoke).toHaveBeenCalledWith("media_subtab", {
    action: "resample",
    params: { input_path: "/pics/a.png", output_path: "/out/custom.png", ...resampleParams, batch: [{ input_path: "/pics/a.png", output_path: "/out/custom.png" }] },
  });
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
  expect(invoke).not.toHaveBeenCalled();
});

test("empty input does not resample", () => {
  render(<SamplerPanel />);
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(invoke).not.toHaveBeenCalled();
  expect(screen.getByText("Status: error: input required")).toBeInTheDocument();
});

test("preflights every destination against every selected source", async () => {
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/in/a.png\n/out/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: failed: refusing to replace a selected source")).toBeInTheDocument();
  expect(invoke).not.toHaveBeenCalled();
});

test("rejects two inputs that would share one output", async () => {
  render(<SamplerPanel />);
  fireEvent.change(screen.getByLabelText("Input"), { target: { value: "/in/a.png\n/other/a.png" } });
  fireEvent.change(screen.getByLabelText("Output"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "Resample" }));
  expect(await screen.findByText("Status: failed: multiple inputs have the same output path")).toBeInTheDocument();
  expect(invoke).not.toHaveBeenCalled();
});
