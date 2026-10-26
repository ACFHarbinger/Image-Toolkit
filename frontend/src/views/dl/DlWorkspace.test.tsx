import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { DlWorkspace } from "./DlWorkspace";

afterEach(() => {
  cleanup();
});

test("inspect shows the run record and does not start a job", async () => {
  const hostClient = {
    dlInspect: vi.fn().mockResolvedValue({
      found: true,
      run_dir: "/runs/one",
      run_id: "run-1",
      status: "running",
      engine: "lora",
      model_id: "sdxl",
      event_count: 2,
      started: false,
      reason: "training is not started",
    }),
  };
  render(<DlWorkspace hostClient={hostClient} route="train" />);
  expect(screen.getByTestId("dl-workspace")).toHaveAttribute("data-route", "train");
  fireEvent.change(screen.getByLabelText("Run directory"), { target: { value: "/runs/one" } });
  fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
  expect(await screen.findByText("run-1 running lora 2 training is not started")).toBeInTheDocument();
  expect(hostClient.dlInspect).toHaveBeenCalledTimes(1);
  expect(hostClient.dlInspect).toHaveBeenCalledWith({ run_dir: "/runs/one" });
});
