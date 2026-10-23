import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { CloudComputeSurface } from "./CloudComputeSurface";
import { CloudJobsControl } from "./CloudJobsControl";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { formatCloudBadge } from "./cloudBadge";

afterEach(cleanup);

test("formats the running count and reserved spend", () => {
  expect(formatCloudBadge({ running: 2, reserved_usd: 4.5, available: true })).toBe("2 · $4.50");
  expect(formatCloudBadge({ running: 0, reserved_usd: 0, available: false })).toBe("—");
});

test("click opens jobs and shift-click or the gear opens compute", () => {
  const onOpenJobs = vi.fn();
  const onOpenCompute = vi.fn();
  render(<CloudJobsControl badge="1 · $1.00" onOpenJobs={onOpenJobs} onOpenCompute={onOpenCompute} />);
  fireEvent.click(screen.getByRole("button", { name: "Cloud Jobs" }));
  expect(onOpenJobs).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "Cloud Jobs" }), { shiftKey: true });
  fireEvent.click(screen.getByRole("button", { name: "Cloud Compute" }));
  expect(onOpenCompute).toHaveBeenCalledTimes(2);
  expect(screen.getByTestId("cloud-jobs-badge")).toHaveTextContent("1 · $1.00");
});

test("the jobs window names the panes later gates fill", () => {
  render(<CloudJobsWindow badge="—" />);
  expect(screen.getByTestId("cloud-jobs-window")).toHaveTextContent("Cloud Jobs");
  expect(screen.getByTestId("cloud-jobs-jobs")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-jobs-detail")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-jobs-resources")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-jobs-spend")).toBeInTheDocument();
});

test("cloud compute is the setup surface", () => {
  const onClose = vi.fn();
  render(<CloudComputeSurface onClose={onClose} />);
  expect(screen.getByTestId("cloud-compute-surface")).toHaveTextContent("Cloud Compute");
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(onClose).toHaveBeenCalledOnce();
});
