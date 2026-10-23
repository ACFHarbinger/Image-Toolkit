import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      />,
    );

    const btn = screen.getByTestId("confirm-submit-button");
    expect(btn).toBeDisabled();

    const checkbox = screen.getByTestId("ack-checkbox-safeguard.spot_unresumable");
    fireEvent.click(checkbox);

    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("RequestBuilder Component (#850)", () => {
  it("loads presets and updates JobSpec parameters", () => {
    render(<RequestBuilder />);
    const selector = screen.getByTestId("preset-selector");

    fireEvent.change(selector, { target: { value: "comfy" } });
    expect(screen.getByTestId("input-workload-kind")).toHaveValue("comfy_batch");

    fireEvent.change(selector, { target: { value: "convert" } });
    expect(screen.getByTestId("input-workload-kind")).toHaveValue("extract");
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

  it("opens PlanCostSheet on review click and dispatches via client", async () => {
    const mockSubmit = vi.fn().mockResolvedValue({ job_id: "cj-dispatched-123" });
    const mockClient = {
      submitJob: mockSubmit,
    } as unknown as HostClient;

    render(<RequestBuilder client={mockClient} />);

    const reviewBtn = screen.getByTestId("review-plan-button");
    fireEvent.click(reviewBtn);

    expect(screen.getByTestId("plan-cost-sheet")).toBeInTheDocument();

    const confirmBtn = screen.getByTestId("confirm-submit-button");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("submit-success-banner")).toBeInTheDocument();
    });
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
