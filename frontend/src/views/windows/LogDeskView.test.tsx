import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LogDeskView } from "./LogDeskView";

afterEach(() => {
  cleanup();
  vi.mocked(invoke).mockReset();
  vi.mocked(invoke).mockImplementation(() => Promise.resolve({}));
});

test("reads the last lines and shows the reason", async () => {
  const hostClient = {
    logsRead: vi.fn().mockResolvedValue({
      found: true,
      path: "/tmp/app.log",
      lines: ["ERROR boom", "done"],
      error_count: 1,
      reason: "log is not followed",
    }),
  };
  render(<LogDeskView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Path"), { target: { value: "/tmp/app.log" } });
  fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Read" }));
  expect(await screen.findByText("log is not followed")).toBeInTheDocument();
  expect(screen.getByText("ERROR boom")).toBeInTheDocument();
  expect(screen.getByText("done")).toBeInTheDocument();
  expect(hostClient.logsRead).toHaveBeenCalledWith({ path: "/tmp/app.log", limit: 2 });
});

test("a scanned log file fills Path", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string, args?: unknown) => {
    if (command === "scan_files" && (args as { directory?: string } | undefined)?.directory === "/var/log") {
      return ["/var/log/app.log"];
    }
    return [];
  });
  const hostClient = { logsRead: vi.fn() };
  render(<LogDeskView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Log directory"), { target: { value: "/var/log" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan" }));
  fireEvent.click(await screen.findByRole("option", { name: "app.log" }));
  expect(screen.getByLabelText("Path")).toHaveValue("/var/log/app.log");
  expect(hostClient.logsRead).not.toHaveBeenCalled();
});

test("copy all copies the lines and clear empties them without reading again", async () => {
  const previous = navigator.clipboard;
  const hostClient = {
    logsRead: vi.fn().mockResolvedValue({
      found: true,
      path: "/tmp/app.log",
      lines: ["ERROR boom", "done"],
      error_count: 1,
      reason: "log is not followed",
    }),
  };
  render(<LogDeskView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Path"), { target: { value: "/tmp/app.log" } });
  fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Read" }));
  expect(await screen.findByText("log is not followed")).toBeInTheDocument();
  expect(screen.getByText("ERROR boom")).toBeInTheDocument();
  expect(screen.getByText("done")).toBeInTheDocument();
  const writeText = vi.fn().mockResolvedValue(undefined);
  navigator.clipboard = { writeText } as Clipboard;
  try {
    fireEvent.click(screen.getByRole("button", { name: "Copy all" }));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("ERROR boom\ndone");
    });
    expect(hostClient.logsRead).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByText("ERROR boom")).not.toBeInTheDocument();
    expect(screen.queryByText("done")).not.toBeInTheDocument();
    expect(screen.getByText("log is not followed")).toBeInTheDocument();
    expect(screen.getByLabelText("Path")).toHaveValue("/tmp/app.log");
    expect(hostClient.logsRead).toHaveBeenCalledTimes(1);
  } finally {
    navigator.clipboard = previous;
  }
});
