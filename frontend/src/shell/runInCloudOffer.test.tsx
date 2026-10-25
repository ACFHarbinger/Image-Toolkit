import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { RunInCloudOffer } from "./RunInCloudOffer";

test("the form asks for a prefill and does not submit", () => {
  const onPrefill = vi.fn();
  render(<RunInCloudOffer offer={null} notice="" onPrefill={onPrefill} />);
  expect(screen.getByText("This does not submit a job.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "train-lora" } });
  fireEvent.change(screen.getByLabelText("Estimated GB"), { target: { value: "9.1" } });
  fireEvent.change(screen.getByLabelText("Device GB"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Run in cloud instead" }));
  expect(onPrefill).toHaveBeenCalledWith("train-lora", 9.1, 10);
  expect(screen.queryByRole("button", { name: /^submit/i })).toBeNull();
});

test("a priced prefill stays unsubmitted", () => {
  render(
    <RunInCloudOffer
      notice="GPU admission refused"
      onPrefill={() => undefined}
      offer={{
        offered: true,
        submitted: false,
        reason: "GPU admission refused",
        estimate_usd: 0.66,
        estimate_known: true,
        kind: "lora_train",
        vram_gb_min: 9.1,
        provider: "gcp",
        region: "us-central1",
        runtime_s: 600,
        job_id: "cj-abc",
        spec: {
          job_id: "cj-abc",
          kind: "lora_train",
          title: "train-lora",
          placement: { provider: "gcp", region: "us-central1", mode: "instance" },
          resources: { vram_gb_min: 9.1 },
          params: { expected_runtime_s: 600 },
        },
      }}
    />,
  );
  expect(screen.getByTestId("run-in-cloud-prefill")).toHaveTextContent("lora_train");
  expect(screen.getByTestId("run-in-cloud-prefill")).toHaveTextContent("$0.66");
  expect(screen.getByTestId("run-in-cloud-prefill")).toHaveTextContent("cj-abc");
  expect(screen.getByTestId("offer-title")).toHaveValue("train-lora");
  expect(screen.getByTestId("offer-provider")).toHaveValue("gcp");
  fireEvent.change(screen.getByTestId("offer-title"), { target: { value: "evening train" } });
  expect(screen.getByTestId("offer-title")).toHaveValue("evening train");
  expect(screen.queryByRole("button", { name: /^submit/i })).toBeNull();
  expect(screen.getByText(/does not save or submit/i)).toBeInTheDocument();
});
