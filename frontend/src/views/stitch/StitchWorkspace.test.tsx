import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { StitchWorkspace } from "./StitchWorkspace";

afterEach(() => {
  cleanup();
});

test("shows the route and the reason without a panorama", async () => {
  const hostClient = {
    stitchStatus: vi.fn().mockResolvedValue({
      route: "stitch.canvas",
      started: false,
      reason: "stitch pipeline is not started",
    }),
  };
  render(<StitchWorkspace route="stitch.canvas" hostClient={hostClient} />);
  expect(screen.getByTestId("stitch-workspace")).toHaveTextContent("stitch.canvas");
  expect(await screen.findByText("stitch pipeline is not started")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Shared canvas host" })).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(hostClient.stitchStatus).toHaveBeenCalledWith("stitch.canvas");
});
