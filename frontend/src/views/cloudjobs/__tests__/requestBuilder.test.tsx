import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CloudJobsPopout } from "../../../shell/CloudJobsPopout";

afterEach(() => {
  cleanup();
});
import type { HostClient } from "../../../hostclient";
import {
  createDefaultJobSpec,
  formatBytes,
  formatUsd,
  jobSpecFromComfy,
  jobSpecFromConvert,
  jobSpecFromExtract,
  validateJobSpec,
} from "../jobSpec";
import { PlanCostSheet } from "../PlanCostSheet";
import { RequestBuilder } from "../RequestBuilder";
import { evaluateRisk, getRiskInputClass } from "../risk";

describe("JobSpec & Origin Presets (#826, #850)", () => {
  it("creates a valid default extract job spec", () => {
    const spec = createDefaultJobSpec("extract");
    expect(spec.kind).toBe("extract");
    expect(spec.placement.mode).toBe("managed_batch");
    expect(spec.shards).toHaveLength(1);
    expect(validateJobSpec(spec)).toEqual([]);
  });

  it("validates shard and limit invariants", () => {
    const spec = createDefaultJobSpec("lora_train");
    spec.shards = [
      { index: 0, params: {} },
      { index: 1, params: {} },
    ];
    const errors = validateJobSpec(spec);
    expect(errors).toContain("LoRA training is a single-shard job.");

    spec.limits.max_spend_usd = -5;
    expect(validateJobSpec(spec)).toContain("max_spend_usd must be positive.");
  });

  it("builds identical JobSpec from Convert origin tab", () => {
    const spec = jobSpecFromConvert({
      inputPaths: ["/tmp/a.png", "/tmp/b.png"],
      outputFormat: "webp",
      provider: "runpod",
    });
    expect(spec.kind).toBe("extract");
    expect(spec.shards).toHaveLength(2);
    expect(spec.params?.output_format).toBe("webp");
    expect(validateJobSpec(spec)).toEqual([]);
  });

  it("builds identical JobSpec from Video Extract origin tab", () => {
    const spec = jobSpecFromExtract({
      mediaPath: "/videos/source.mp4",
      startMs: 0,
      endMs: 10000,
      fps: 24,
      resolution: "1080p",
    });
    expect(spec.kind).toBe("extract");
    expect(spec.params?.fps).toBe(24);
    expect(spec.shards.length).toBeGreaterThan(0);
    expect(validateJobSpec(spec)).toEqual([]);
  });

  it("builds identical JobSpec from ComfyUI origin tab", () => {
    const spec = jobSpecFromComfy({
      workflow: { sampler: "euler" },
      prompts: ["cat", "dog"],
    });
    expect(spec.kind).toBe("comfy_batch");
    expect(spec.placement.mode).toBe("instance");
    expect(spec.shards).toHaveLength(2);
    expect(validateJobSpec(spec)).toEqual([]);
  });

  it("formats bytes and USD accurately", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatUsd(12.345)).toBe("$12.35");
  });
});

describe("Risk Rules Evaluation (#830, #850)", () => {
  it("blocks sensitive data dispatched to unallowlisted providers", () => {
    const spec = createDefaultJobSpec("extract");
    spec.data_class = "sensitive";
    spec.placement.provider = "untrusted_cloud";

    const diag = evaluateRisk(spec, { sensitiveAllowlist: ["gcp", "aws"] });
    expect(diag.blocking.length).toBeGreaterThan(0);
    expect(diag.blocking.some((f) => f.rule_id === "sec.sensitive_allowlist")).toBe(true);
    expect(diag.severity_of("placement.provider")).toBe("block");
    expect(diag.ok_to_submit(new Set())).toBe(false);
  });

  it("warns when spot instances are enabled on unresumable jobs and requires ack", () => {
    const spec = createDefaultJobSpec("extract");
    spec.limits.spot_allowed = true;

    const diag = evaluateRisk(spec);
    expect(diag.blocking).toHaveLength(0);
    expect(diag.needs_ack).toContain("safeguard.spot_unresumable");
    expect(diag.severity_of("limits.spot_allowed")).toBe("warn");
    expect(diag.ok_to_submit(new Set())).toBe(false);
    expect(diag.ok_to_submit(new Set(["safeguard.spot_unresumable"]))).toBe(true);
  });

  it("greys out and blocks unsupported GPU execution modes", () => {
    const spec = createDefaultJobSpec("comfy_batch");
    spec.placement.provider = "azure";
    spec.placement.mode = "managed_batch";
    spec.resources.gpu_class = "NVIDIA-A100";
    spec.resources.gpu_count = 1;

    const diag = evaluateRisk(spec);
    expect(diag.disabled_fields.has("placement.mode")).toBe(true);
    expect(diag.blocking.some((f) => f.rule_id === "cap.gpu_mode_unsupported")).toBe(true);
  });

  it("returns appropriate Tailwind classes by severity level", () => {
    expect(getRiskInputClass("block")).toContain("border-red-500 bg-red-50");
    expect(getRiskInputClass("warn")).toContain("border-amber-500 bg-amber-50");
    expect(getRiskInputClass("info")).toContain("border-blue-400 bg-blue-50");
    expect(getRiskInputClass(null)).toContain("border-gray-300");
  });
});

describe("PlanCostSheet Component (#850)", () => {
  it("renders job details and cost breakdown", () => {
    const spec = createDefaultJobSpec("extract");
    const diag = evaluateRisk(spec);
    render(
      <PlanCostSheet
        spec={spec}
        diagnosis={diag}
        onConfirmSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("plan-cost-sheet")).toBeInTheDocument();
    expect(screen.getByText("Plan & Cost Confirmation")).toBeInTheDocument();
    expect(screen.getByText(spec.job_id)).toBeInTheDocument();
    expect(screen.getByText("Estimated Total Job Cost Breakdown")).toBeInTheDocument();
    expect(screen.getByTestId("pricing-unknown")).toBeInTheDocument();
    expect(screen.getByTestId("submission-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-submit-button")).toBeDisabled();
  });

  it("shows the backend breakdown when the catalogue knows the price", () => {
    const spec = createDefaultJobSpec("extract");
    const diag = evaluateRisk(spec);
    render(
      <PlanCostSheet
        spec={spec}
        diagnosis={diag}
        onConfirmSubmit={vi.fn()}
        onClose={vi.fn()}
        estimateKnown
        submissionAvailable
        estimate={{
          compute: 1.2,
          startup: 0.1,
          ipv4: 0,
          storage: 0,
          egress: 0.04,
          retries: 0.1,
          total: 1.44,
        }}
      />,
    );
    expect(screen.getByText("$1.20")).toBeInTheDocument();
    expect(screen.getByText("$1.44")).toBeInTheDocument();
    expect(screen.queryByTestId("pricing-unknown")).not.toBeInTheDocument();
  });

  it("disables submit button and shows banner when blocking finding exists", () => {
    const spec = createDefaultJobSpec("extract");
    spec.data_class = "sensitive";
    spec.placement.provider = "untrusted";
    const diag = evaluateRisk(spec, { sensitiveAllowlist: ["gcp"] });

    render(
      <PlanCostSheet
        spec={spec}
        diagnosis={diag}
        onConfirmSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("blocking-banner")).toBeInTheDocument();
    const btn = screen.getByTestId("confirm-submit-button");
    expect(btn).toBeDisabled();
  });

  it("enables submit once required risk acknowledgments are checked", () => {
    const spec = createDefaultJobSpec("extract");
    spec.limits.spot_allowed = true;
    const diag = evaluateRisk(spec);

    const onConfirm = vi.fn();
    render(
      <PlanCostSheet
        spec={spec}
        diagnosis={diag}
        onConfirmSubmit={onConfirm}
        onClose={vi.fn()}
        submissionAvailable
      />,
    );

    const btn = screen.getByTestId("confirm-submit-button");
    expect(btn).toBeDisabled();

    const checkbox = screen.getByTestId("ack-checkbox-safeguard.spot_unresumable");
    fireEvent.click(checkbox);

    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledWith(["safeguard.spot_unresumable"]);
  });
});

describe("RequestBuilder Component (#850)", () => {
  it("keeps origin presets disabled until a real selection is passed in", () => {
    render(<RequestBuilder />);
    const selector = screen.getByTestId("preset-selector");
    expect(within(selector).getByRole("option", { name: "Convert Tab Selection" })).toBeDisabled();
    expect(within(selector).getByRole("option", { name: "Video Extractor Selection" })).toBeDisabled();
    expect(within(selector).getByRole("option", { name: "ComfyUI Generation Batch" })).toBeDisabled();
    expect(screen.getByTestId("preset-origin-note")).toHaveTextContent(/do not substitute sample files/i);

    fireEvent.change(selector, { target: { value: "comfy" } });
    expect(selector).toHaveValue("custom");
    expect(screen.getByTestId("input-workload-kind")).toHaveValue("extract");
    expect(screen.getByTestId("input-job-title")).toHaveValue("");
  });

  it("loads presets from the caller's origin selection", () => {
    render(
      <RequestBuilder
        origins={{
          convert: { inputPaths: ["/library/page.webp"], outputFormat: "png" },
          extract: {
            mediaPath: "/library/episode.mp4",
            startMs: 0,
            endMs: 2000,
            fps: 12,
            resolution: "1280x720",
          },
          comfy: { workflow: { sampler: "euler" }, prompts: ["city night"] },
        }}
      />,
    );
    const selector = screen.getByTestId("preset-selector");

    fireEvent.change(selector, { target: { value: "comfy" } });
    expect(screen.getByTestId("input-workload-kind")).toHaveValue("comfy_batch");
    expect(screen.getByTestId("input-job-title")).toHaveValue("ComfyUI Batch (1 prompts)");

    fireEvent.change(selector, { target: { value: "convert" } });
    expect(screen.getByTestId("input-workload-kind")).toHaveValue("extract");
    expect(screen.getByTestId("input-job-title")).toHaveValue("Batch Convert to .png (1 items)");
    expect(screen.getByTestId("input-shards-count")).toHaveValue(1);

    fireEvent.change(selector, { target: { value: "extract" } });
    expect(screen.getByTestId("input-job-title")).toHaveValue("Extract Frames: episode.mp4");
  });

  it("recolors inputs dynamically upon risk triggers", () => {
    render(<RequestBuilder />);
    const dataClassSelect = screen.getByTestId("input-data-class");
    const providerSelect = screen.getByTestId("input-provider");

    // Setting untrusted provider + sensitive data triggers block styling
    fireEvent.change(providerSelect, { target: { value: "hyperstack" } });
    fireEvent.change(dataClassSelect, { target: { value: "sensitive" } });

    expect(providerSelect.className).toContain("border-red-500");
    expect(screen.getByTestId("field-risk-placement.provider")).toBeInTheDocument();
  });

  it("opens PlanCostSheet on review click and dispatches via the cloud service", async () => {
    const mockSubmit = vi.fn().mockResolvedValue({
      accepted: true,
      job_id: "cj-dispatched-123",
      reason: "",
    });
    const mockClient = {
      cloudJobsPreview: vi.fn().mockResolvedValue({
        available: true,
        issues: [],
        needs_ack: [],
        estimate_known: true,
        estimate: {
          compute: 1.2,
          startup: 0.1,
          ipv4: 0,
          storage: 0,
          egress: 0,
          retries: 0.1,
          total: 1.4,
        },
        reason: "",
      }),
      cloudJobsSubmit: mockSubmit,
    } as unknown as HostClient;

    render(<RequestBuilder client={mockClient} />);
    fireEvent.click(screen.getByTestId("review-plan-button"));
    expect(screen.getByTestId("plan-cost-sheet")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("$1.40")).toBeInTheDocument();
      expect(screen.getByTestId("confirm-submit-button")).toBeEnabled();
    });
    fireEvent.click(screen.getByTestId("confirm-submit-button"));
    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("submit-success-banner")).toBeInTheDocument();
    });
  });

  it("does not dispatch when the cloud service is absent", () => {
    render(<RequestBuilder />);
    fireEvent.click(screen.getByTestId("review-plan-button"));
    expect(screen.getByTestId("submission-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-submit-button")).toBeDisabled();
    expect(screen.queryByTestId("submit-success-banner")).not.toBeInTheDocument();
  });

  it("leaves the execution mode selector usable when managed batch is unsupported", () => {
    render(<RequestBuilder />);
    fireEvent.change(screen.getByTestId("input-provider"), { target: { value: "azure" } });
    fireEvent.change(screen.getByTestId("input-gpu-class"), { target: { value: "NVIDIA-A100" } });
    const mode = screen.getByTestId("input-execution-mode");
    expect(mode).toBeEnabled();
    expect(within(mode).getByRole("option", { name: /Managed Batch/ })).toBeDisabled();
    fireEvent.change(mode, { target: { value: "instance" } });
    expect(mode).toHaveValue("instance");
  });

  it("mounts RequestBuilder inside CloudJobsPopout with tab switching", () => {
    render(<CloudJobsPopout />);
    expect(screen.getByTestId("cloud-jobs-popout")).toBeInTheDocument();
    expect(screen.getByTestId("cloud-jobs-request-builder")).toBeInTheDocument();

    const jobsTab = screen.getByTestId("tab-jobs-queue");
    fireEvent.click(jobsTab);
    expect(screen.getByTestId("cloud-jobs-queue-view")).toBeInTheDocument();
    expect(screen.queryByTestId("cloud-jobs-request-builder")).not.toBeInTheDocument();

    const builderTab = screen.getByTestId("tab-request-builder");
    fireEvent.click(builderTab);
    expect(screen.getByTestId("cloud-jobs-request-builder")).toBeInTheDocument();
  });
});


it("renders backend-only acknowledgments and submits their authoritative IDs", async () => {
  const cloudJobsSubmit = vi.fn().mockResolvedValue({ accepted: true, job_id: "accepted", reason: "" });
  const client = {
    cloudJobsPreview: vi.fn().mockResolvedValue({ available: true, estimate_known: false, estimate: null,
      issues: [{ stage: "policy", severity: "warn", message: "Estimate unavailable", ack_id: "pol.no_estimate", targets: [] }],
      needs_ack: ["pol.no_estimate", "pol.reduced_protection"] }), cloudJobsSubmit,
  } as unknown as HostClient;
  render(<RequestBuilder client={client} />);
  fireEvent.click(screen.getByTestId("review-plan-button"));
  await screen.findByTestId("ack-checkbox-pol.no_estimate");
  expect(screen.getByText("Estimate unavailable")).toBeInTheDocument();
  expect(screen.getByTestId("confirm-submit-button")).toBeDisabled();
  fireEvent.click(screen.getByTestId("ack-checkbox-pol.no_estimate"));
  expect(screen.getByTestId("confirm-submit-button")).toBeDisabled();
  fireEvent.click(screen.getByTestId("ack-checkbox-pol.reduced_protection"));
  fireEvent.click(screen.getByTestId("confirm-submit-button"));
  await waitFor(() => expect(cloudJobsSubmit).toHaveBeenCalledTimes(1));
  expect(cloudJobsSubmit.mock.calls[0][0].acknowledged.sort()).toEqual(["pol.no_estimate", "pol.reduced_protection"]);
});

it("keeps authoritative blocking findings blocked", async () => {
  const client = { cloudJobsPreview: vi.fn().mockResolvedValue({ available: true, estimate_known: false, estimate: null,
    issues: [{ stage: "budget", severity: "block", message: "Account cap exceeded", ack_id: null, targets: [] }], needs_ack: [] }) } as unknown as HostClient;
  render(<RequestBuilder client={client} />);
  fireEvent.click(screen.getByTestId("review-plan-button"));
  await screen.findByText("Account cap exceeded");
  expect(screen.getByTestId("confirm-submit-button")).toBeDisabled();
});


it("retains the job ID on refusal and renews it only after acceptance", async () => {
  const cloudJobsSubmit = vi.fn()
    .mockResolvedValueOnce({ accepted: false, job_id: "", reason: "Retry later" })
    .mockResolvedValueOnce({ accepted: true, job_id: "first-accepted", reason: "" })
    .mockResolvedValueOnce({ accepted: true, job_id: "second-accepted", reason: "" });
  const onJobSubmitted = vi.fn();
  const client = {
    cloudJobsPreview: vi.fn().mockResolvedValue({ available: true, estimate_known: false,
      estimate: null, issues: [], needs_ack: [] }), cloudJobsSubmit,
  } as unknown as HostClient;
  render(<RequestBuilder client={client} onJobSubmitted={onJobSubmitted} />);
  fireEvent.change(screen.getByTestId("input-job-title"), { target: { value: "Keep these parameters" } });
  fireEvent.click(screen.getByTestId("review-plan-button"));
  await waitFor(() => expect(screen.getByTestId("confirm-submit-button")).toBeEnabled());
  fireEvent.click(screen.getByTestId("confirm-submit-button"));
  await screen.findByText(/Retry later/);
  const firstId = cloudJobsSubmit.mock.calls[0][0].spec.job_id;
  fireEvent.click(screen.getByTestId("confirm-submit-button"));
  await screen.findByTestId("submit-success-banner");
  expect(cloudJobsSubmit.mock.calls[1][0].spec.job_id).toBe(firstId);
  expect(onJobSubmitted.mock.calls[0][1].job_id).toBe(firstId);
  fireEvent.click(screen.getByTestId("review-plan-button"));
  await waitFor(() => expect(screen.getByTestId("confirm-submit-button")).toBeEnabled());
  fireEvent.click(screen.getByTestId("confirm-submit-button"));
  await waitFor(() => expect(cloudJobsSubmit).toHaveBeenCalledTimes(3));
  const nextSpec = cloudJobsSubmit.mock.calls[2][0].spec;
  expect(nextSpec.job_id).not.toBe(firstId);
  expect(nextSpec.title).toBe("Keep these parameters");
});
