import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ConvertPilot } from "./ConvertPilot";

afterEach(() => {
  cleanup();
});

test("single convert still calls convert.convert", async () => {
  const hostClient = {
    convert: vi.fn().mockResolvedValue({ success: true, error: null }),
    convertListDir: vi.fn(),
    convertBatch: vi.fn(),
    jobStatus: vi.fn(),
    cancelJob: vi.fn(),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Input path"), { target: { value: "/pics/a.png" } });
  fireEvent.change(screen.getByLabelText("Output path"), { target: { value: "/tmp/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Convert" }));
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  expect(hostClient.convert).toHaveBeenCalledWith({
    input_path: "/pics/a.png",
    output_path: "/tmp/out.png",
    output_format: "png",
    quality: 95,
  });
  expect(hostClient.convertBatch).not.toHaveBeenCalled();
});

test("lists a directory and resamples the selection", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn().mockResolvedValue({ files: ["/dir/a.png", "/dir/b.png"], error: "" }),
    convertBatch: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    jobStatus: vi.fn().mockResolvedValue({
      job_id: "job-1",
      kind: "convert.batch",
      state: "completed",
      progress: { done: 1, total: 1 },
    }),
    cancelJob: vi.fn().mockResolvedValue({ ok: true }),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "List files" }));
  expect(await screen.findByLabelText("/dir/a.png")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("/dir/b.png"));
  fireEvent.click(screen.getByRole("button", { name: "Resample Selected" }));
  expect(await screen.findByText("Progress: 1/1")).toBeInTheDocument();
  expect(hostClient.convertBatch).toHaveBeenCalledWith(
    expect.objectContaining({
      input_dir: "/dir",
      output_dir: "/out",
      action: "resample",
      paths: ["/dir/a.png"],
      width: 64,
      height: 64,
      algorithm: "lanczos",
    }),
  );
});

test("cancel asks the job to stop", async () => {
  let release: (value: unknown) => void = () => undefined;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn().mockResolvedValue({ files: ["/dir/a.png"], error: "" }),
    convertBatch: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    jobStatus: vi.fn().mockReturnValue(pending),
    cancelJob: vi.fn().mockResolvedValue({ ok: true }),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "List files" }));
  expect(await screen.findByLabelText("/dir/a.png")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Re-encode Selected" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(hostClient.cancelJob).toHaveBeenCalledWith("job-1"));
  release({ job_id: "job-1", kind: "convert.batch", state: "cancelled", progress: { done: 0, total: 1 } });
  expect(await screen.findByText("Status: cancelled")).toBeInTheDocument();
});
