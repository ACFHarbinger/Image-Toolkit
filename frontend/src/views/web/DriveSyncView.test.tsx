import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { DriveSyncView } from "./DriveSyncView";

afterEach(() => {
  cleanup();
});

test("plan stays unsent", async () => {
  const hostClient = {
    driveSyncPlan: vi.fn().mockResolvedValue({
      submitted: false,
      provider: "dropbox",
      count: 1,
      reason: "sync is not sent",
    }),
  };
  render(<DriveSyncView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "dropbox" } });
  fireEvent.change(screen.getByLabelText("Paths"), { target: { value: "/a.png\n" } });
  fireEvent.click(screen.getByRole("button", { name: "Plan" }));
  expect(await screen.findByText("dropbox 1 sync is not sent")).toBeInTheDocument();
  expect(hostClient.driveSyncPlan).toHaveBeenCalledWith({ provider: "dropbox", paths: ["/a.png"] });
});
