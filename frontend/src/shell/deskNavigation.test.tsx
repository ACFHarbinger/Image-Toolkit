import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { AppStoreProvider } from "../store/AppStoreProvider";

expect.extend(matchers);
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.mocked(invoke).mockReset();
});

test("diagnostics navigation mounts both desk views with the shell client", async () => {
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    if (command !== "bridge_request") return {};
    const { request } = args as { request: { id: string; method: string } };
    const result = request.method === "system.handshake"
      ? { protocol: "image-toolkit-bridge", version: "1.0.0", compatibility: { min: "1.0.0", max: "1.0.0" }, capabilities: ["system", "desk"] }
      : request.method === "logs.read"
        ? { found: true, path: "/tmp/app.log", lines: ["desk log output"], error_count: 0, reason: "read complete" }
        : { found: true, path: "/tmp/file.png", name: "file.png", size: 42, suffix: ".png", reason: "metadata complete" };
    return { jsonrpc: "2.0", id: request.id, result };
  });
  localStorage.setItem("app_authenticated", "true");
  localStorage.setItem("app_account_name", "TestUser");
  render(<AppStoreProvider><App /></AppStoreProvider>);
  fireEvent.change(await screen.findByLabelText("Category"), { target: { value: "Developer / Diagnostics" } });
  fireEvent.click(screen.getByRole("tab", { name: "Logs" }));
  fireEvent.change(screen.getByLabelText("Path"), { target: { value: "/tmp/app.log" } });
  fireEvent.click(screen.getByRole("button", { name: "Read" }));
  expect(await screen.findByText("desk log output")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "File Metadata" }));
  fireEvent.change(screen.getByLabelText("Path"), { target: { value: "/tmp/file.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Describe" }));
  expect(await screen.findByText("metadata complete")).toBeInTheDocument();
  await waitFor(() => expect(vi.mocked(invoke).mock.calls.some(([, args]) =>
    (args as { request?: { method?: string } })?.request?.method === "metadata.describe",
  )).toBe(true));
});
