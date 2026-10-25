import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ResourcesView, SpendView, money } from "./CloudJobsViews";

test("money formats ledger amounts", () => {
  expect(money(1.5)).toBe("$1.50");
});

test("orphans can be terminated and spend lists providers", () => {
  const onTerminate = vi.fn();
  render(
    <>
      <ResourcesView
        notice=""
        onTerminate={onTerminate}
        view={{
          available: true,
          resources: [
            {
              provider: "gcp",
              kind: "instance",
              resource_id: "inst-1",
              region: "us-central1",
              job_id: "",
              orphan: true,
            },
            {
              provider: "gcp",
              kind: "instance",
              resource_id: "inst-2",
              region: "us-central1",
              job_id: "job-1",
              orphan: false,
            },
          ],
        }}
      />
      <SpendView
        view={{
          available: true,
          month_actual_usd: 3.5,
          reserved_usd: 4,
          by_provider: [{ provider: "gcp", actual_usd: 3.5 }],
        }}
      />
    </>,
  );
  expect(screen.getByTestId("cloud-jobs-resources")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-jobs-month-spend")).toHaveTextContent("This month $3.50 · reserved $4.00");
  expect(screen.getByText("gcp $3.50")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
  expect(onTerminate).toHaveBeenCalledWith("inst-1");
  expect(screen.getAllByRole("button", { name: "Terminate" })).toHaveLength(1);
});

test("missing projections say the views are unavailable", () => {
  render(
    <>
      <ResourcesView notice="" onTerminate={() => {}} view={{ available: false, resources: [] }} />
      <SpendView
        view={{ available: false, month_actual_usd: 0, reserved_usd: 0, by_provider: [] }}
      />
    </>,
  );
  expect(screen.getByText("Resources unavailable")).toBeInTheDocument();
  expect(screen.getByText("Spend unavailable")).toBeInTheDocument();
});
