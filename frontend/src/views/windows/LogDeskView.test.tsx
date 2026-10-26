import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LogDeskView } from "./LogDeskView";

afterEach(() => {
  cleanup();
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
