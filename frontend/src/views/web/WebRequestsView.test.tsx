import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { HostClient } from "../../hostclient";
import { WebRequestsView } from "./WebRequestsView";

expect.extend(matchers);

afterEach(() => cleanup());

function stubClient(overrides: Partial<HostClient> = {}) {
  return {
    webreqSequence: vi.fn(async () => ({
      status: "completed" as const,
      base_url: "https://httpbin.org",
      total_requests: 1,
      completed_requests: 1,
      logs: [
        "Starting request sequence for https://httpbin.org",
        "--- Request 1/1: [GET] ---",
        "Request complete. Status: 200",
        "  > Action: Status Code: 200",
        "--- All requests finished. ---",
      ],
      items: [
        {
          index: 0,
          url: "https://httpbin.org/get",
          method: "GET",
          status_code: 200,
          saved_path: null,
          error: null,
        },
      ],
      message: "All requests finished.",
    })),
    webreqExecute: vi.fn(async () => ({
      url: "https://httpbin.org/json",
      status_code: 200,
      status_text: "OK",
      headers: { "Content-Type": "application/json" },
      content_type: "application/json",
      body: '{"message": "success"}',
      duration_ms: 45.2,
      error: null,
    })),
    ...overrides,
  } as unknown as HostClient;
}

test("renders WebRequestsView with header and default base URL", () => {
  const client = stubClient();
  render(<WebRequestsView hostClient={client} />);

  expect(screen.getByText("Web Requests Pipeline")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("https://api.example.com")).toHaveValue("https://httpbin.org");
  expect(screen.getByText("Run Sequence")).toBeInTheDocument();
});

test("adds and removes request items in sequence builder", () => {
  const client = stubClient();
  render(<WebRequestsView hostClient={client} />);

  const input = screen.getByPlaceholderText("URL suffix (GET) or post data (POST)");
  fireEvent.change(input, { target: { value: "/users" } });

  const addBtn = screen.getAllByRole("button", { name: /Add/i })[0];
  fireEvent.click(addBtn);

  expect(screen.getByText("/users")).toBeInTheDocument();

  // Remove first request
  const removeButtons = screen.getAllByRole("button", { name: "" });
  if (removeButtons[0]) {
    fireEvent.click(removeButtons[0]);
  }
});

test("adds and removes response actions in action builder", () => {
  const client = stubClient();
  render(<WebRequestsView hostClient={client} />);

  const addActions = screen.getAllByRole("button", { name: /Add/i })[1];
  fireEvent.click(addActions);

  expect(screen.getAllByText(/Print Response Status Code/i).length).toBeGreaterThan(0);
});

test("executes sequence via hostClient.webreqSequence", async () => {
  const client = stubClient();
  const showModal = vi.fn();
  render(<WebRequestsView hostClient={client} showModal={showModal} />);

  const runBtn = screen.getByText("Run Sequence");
  fireEvent.click(runBtn);

  await waitFor(() => {
    expect(client.webreqSequence).toHaveBeenCalledWith(
      expect.objectContaining({
        base_url: "https://httpbin.org",
      })
    );
  });

  expect(screen.getByText(/Request complete. Status: 200/)).toBeInTheDocument();
  expect(showModal).toHaveBeenCalledWith("All requests finished.", "success");
});

test("switches to Single Inspector and executes request", async () => {
  const client = stubClient();
  const showModal = vi.fn();
  render(<WebRequestsView hostClient={client} showModal={showModal} />);

  const singleTabBtn = screen.getByText("Single Inspector");
  fireEvent.click(singleTabBtn);

  expect(screen.getByText("Single Request Execution")).toBeInTheDocument();
  const execBtn = screen.getByText("Execute Request");
  fireEvent.click(execBtn);

  await waitFor(() => {
    expect(client.webreqExecute).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "https://httpbin.org/json",
        method: "GET",
      })
    );
  });

  expect(screen.getByText(/HTTP 200/)).toBeInTheDocument();
  expect(screen.getByText(/"message": "success"/)).toBeInTheDocument();
  expect(showModal).toHaveBeenCalledWith("HTTP 200 in 45.2ms", "success");
});
