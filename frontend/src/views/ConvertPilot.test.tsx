import { open } from "@tauri-apps/plugin-dialog";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ConvertPilot } from "./ConvertPilot";

afterEach(() => {
  cleanup();
});

test("browse buttons fill directory fields without listing or converting", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn(),
    convertBatch: vi.fn(),
    jobStatus: vi.fn(),
    cancelJob: vi.fn(),
  };
  vi.mocked(open).mockResolvedValueOnce("/picked/in");
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.click(screen.getByRole("button", { name: "Browse directory" }));
  await waitFor(() => expect(screen.getByLabelText("Directory")).toHaveValue("/picked/in"));
  expect(hostClient.convert).not.toHaveBeenCalled();
  expect(hostClient.convertListDir).not.toHaveBeenCalled();
  expect(hostClient.convertBatch).not.toHaveBeenCalled();
  vi.mocked(open).mockResolvedValueOnce("/picked/out");
  fireEvent.click(screen.getByRole("button", { name: "Browse output directory" }));
  await waitFor(() => expect(screen.getByLabelText("Output directory")).toHaveValue("/picked/out"));
});

test("browse file buttons fill single-file paths without converting", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn(),
    convertBatch: vi.fn(),
    jobStatus: vi.fn(),
    cancelJob: vi.fn(),
  };
  vi.mocked(open).mockResolvedValueOnce("/pics/a.png").mockResolvedValueOnce("/tmp/out.png");
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.click(screen.getByRole("button", { name: "Browse input file" }));
  await waitFor(() => expect(screen.getByLabelText("Input path")).toHaveValue("/pics/a.png"));
  fireEvent.click(screen.getByRole("button", { name: "Browse output file" }));
  await waitFor(() => expect(screen.getByLabelText("Output path")).toHaveValue("/tmp/out.png"));
  expect(hostClient.convert).not.toHaveBeenCalled();
  expect(hostClient.convertListDir).not.toHaveBeenCalled();
  expect(hostClient.convertBatch).not.toHaveBeenCalled();
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
  expect(hostClient.convertBatch.mock.calls[0]?.[0].output_format).toBeUndefined();
  fireEvent.click(screen.getByRole("checkbox", { name: "Keep original format" }));
  fireEvent.click(screen.getByRole("button", { name: "Resample Selected" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalledTimes(2));
  expect(hostClient.convertBatch.mock.calls[1]?.[0].output_format).toBe("png");
});

test("select all unions visible files and deselect all clears the selection", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn().mockResolvedValue({ files: ["/dir/a.png", "/dir/b.png"], error: "" }),
    convertBatch: vi.fn(),
    jobStatus: vi.fn(),
    cancelJob: vi.fn(),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "List files" }));
  expect(await screen.findByRole("checkbox", { name: "/dir/a.png" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "/dir/b.png" }));
  expect(screen.getByRole("checkbox", { name: "/dir/b.png" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Select All" }));
  expect(screen.getByRole("checkbox", { name: "/dir/a.png" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "/dir/b.png" })).toBeChecked();
  expect(hostClient.convertListDir).toHaveBeenCalledTimes(1);
  expect(hostClient.convertBatch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Deselect All" }));
  expect(screen.getByRole("checkbox", { name: "/dir/a.png" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "/dir/b.png" })).not.toBeChecked();
  expect(hostClient.convertBatch).not.toHaveBeenCalled();
  expect(hostClient.convertListDir).toHaveBeenCalledTimes(1);
});

test("a completed batch with file failures is not batch ok", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn().mockResolvedValue({ files: ["/dir/a.png"], error: "" }),
    convertBatch: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    jobStatus: vi.fn().mockResolvedValue({
      job_id: "job-1",
      kind: "convert.batch",
      state: "completed",
      result: { succeeded: 0, failed: 1, errors: ["corrupt image"], total_discovered: 1 },
    }),
    cancelJob: vi.fn(),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "List files" }));
  expect(await screen.findByLabelText("/dir/a.png")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Convert Selected" }));
  expect(await screen.findByText("Status: batch failed: 0 succeeded, 1 failed: corrupt image")).toBeInTheDocument();
  expect(screen.queryByText("Status: batch ok")).not.toBeInTheDocument();
});

test("converts a directory without a file selection", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn(),
    convertBatch: vi.fn().mockResolvedValue({ job_id: "job-dir" }),
    jobStatus: vi.fn().mockResolvedValue({
      job_id: "job-dir",
      kind: "convert.batch",
      state: "completed",
      progress: { done: 0, total: 0 },
    }),
    cancelJob: vi.fn(),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "Convert directory" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalledTimes(1));
  expect(hostClient.convertBatch.mock.calls[0]?.[0]).toEqual({
    input_dir: "/dir",
    output_dir: "/out",
    output_format: "png",
    quality: 95,
    overwrite: true,
    action: "convert",
    recursive: false,
    input_formats: ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff", "tif", "ico"],
  });
  fireEvent.click(screen.getByRole("button", { name: "png" }));
  fireEvent.click(screen.getByRole("button", { name: "Convert directory" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalledTimes(2));
  expect(hostClient.convertBatch.mock.calls[1]?.[0].input_formats).toEqual(["png"]);
  fireEvent.click(screen.getByRole("checkbox", { name: "Recursive" }));
  fireEvent.click(screen.getByRole("button", { name: "Convert directory" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalledTimes(3));
  expect(hostClient.convertBatch.mock.calls[2]?.[0].recursive).toBe(true);
});

test("filters listed files by the selected input format chips", async () => {
  const hostClient = {
    convert: vi.fn(),
    convertListDir: vi.fn().mockResolvedValue({ files: ["/dir/a.png", "/dir/b.jpg"], error: "" }),
    convertBatch: vi.fn().mockResolvedValue({ job_id: "job-filter" }),
    jobStatus: vi.fn().mockResolvedValue({
      job_id: "job-filter",
      kind: "convert.batch",
      state: "completed",
      progress: { done: 1, total: 1 },
    }),
    cancelJob: vi.fn(),
  };
  render(<ConvertPilot hostClient={hostClient as never} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.change(screen.getByLabelText("Output directory"), { target: { value: "/out" } });
  fireEvent.click(screen.getByRole("button", { name: "List files" }));
  expect(await screen.findByLabelText("/dir/a.png")).toBeInTheDocument();
  expect(screen.getByLabelText("/dir/b.jpg")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "png" }));
  expect(screen.queryByLabelText("/dir/b.jpg")).not.toBeInTheDocument();
  expect(screen.getByLabelText("/dir/a.png")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Convert Selected" }));
  await waitFor(() => expect(hostClient.convertBatch).toHaveBeenCalledTimes(1));
  expect(hostClient.convertBatch.mock.calls[0]?.[0].paths).toEqual(["/dir/a.png"]);
  expect(hostClient.convertListDir).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Remove all input formats" }));
  expect(screen.getByLabelText("/dir/b.jpg")).toBeInTheDocument();
  expect(hostClient.convertListDir).toHaveBeenCalledTimes(1);
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
