import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { GetResult, ProvidersResult, ResourcesResult, SpendResult, TerminateResult } from "../../../contracts/generated/ts";
import { CloudComputeSurface } from "./CloudComputeSurface";

afterEach(() => cleanup());

const providers: ProvidersResult = {
  providers: [
    {
      provider_id: "gcd",
      name: "Google Cloud Run (GCD)",
      badge_text: "Active PoC Target",
      badge_token: "success",
      description: "Serverless container compute powered by Knative.",
      target_service: "Cloud Run (Knative)",
      cpu_shapes: "4 vCPU (Flex Gen2)",
      memory_tiers: "16 GiB RAM",
      gpu_options: "NVIDIA L4 24GB (Optional)",
      cost_estimate: "~$0.09 / hr (Per-second billing)",
      cold_start: "~1.2s (Gen2 container)",
      regions: ["us-central1 (Iowa)"],
      config_file: "infra/cloud/gcd/cloud-run-service.yaml",
      is_poc_target: true,
    },
    {
      provider_id: "cloudflare",
      name: "Cloudflare Workers & Queues",
      badge_text: "Planned / Edge Queue",
      badge_token: "accent_hover",
      description: "Edge queue consumer.",
      target_service: "Workers + R2 + D1",
      cpu_shapes: "128 MB V8 Isolate",
      memory_tiers: "Unmetered Edge I/O",
      gpu_options: "Cloudflare AI / Partner API",
      cost_estimate: "$5/mo base + $0.50/M ops",
      cold_start: "~5ms (V8 Isolate)",
      regions: ["Global Edge (300+ PoPs)"],
      config_file: "infra/cloud/cloudflare/wrangler.toml",
      is_poc_target: false,
    },
  ],
};

function stubClient(stored: Record<string, unknown> | null = null) {
  return {
    cloudSetupProviders: vi.fn(async (): Promise<ProvidersResult> => providers),
    getSetting: vi.fn(
      async (params: { key: string }): Promise<GetResult> => ({
        key: params.key,
        value: stored as GetResult["value"],
        scope: "account",
      }),
    ),
    setSetting: vi.fn(async (params: { key: string; value: unknown }) => ({
      key: params.key,
      value: params.value,
      scope: "account",
    })),
    cloudJobsResources: vi.fn(async (): Promise<ResourcesResult> => ({ available: false, resources: [] }) as never),
    cloudJobsSpend: vi.fn(async (): Promise<SpendResult> => ({
      available: true,
      month_actual_usd: 12.5,
      reserved_usd: 4,
      by_provider: [{ provider: "gcd", actual_usd: 12.5 }],
    }) as never),
  };
}

test("loads the provider catalog over cloud_setup.providers", async () => {
  const client = stubClient();
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);

  expect(await screen.findByTestId("cloud-provider-card-gcd")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-provider-badge-gcd")).toHaveTextContent("Active PoC Target");
  expect(screen.getByTestId("cloud-provider-card-cloudflare")).toBeInTheDocument();
  expect(screen.getByText(/Cloud Run \(Knative\)/)).toBeInTheDocument();
  expect(client.getSetting).toHaveBeenCalledWith({ key: "cloud_setup/profiles" });
});

test("the credentials tab persists non-secret setup config through settings", async () => {
  const client = stubClient();
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);
  await screen.findByTestId("cloud-provider-card-gcd");

  fireEvent.click(screen.getByTestId("cloud-compute-tab-credentials"));
  const region = await screen.findByLabelText("Preferred region");
  fireEvent.change(region, { target: { value: "europe-west1 (Belgium)" } });
  fireEvent.click(screen.getByRole("button", { name: "Save setup config" }));

  await waitFor(() => {
    expect(client.setSetting).toHaveBeenCalledWith({
      key: "cloud_setup/profiles",
      value: { gcd: { region: "europe-west1 (Belgium)", endpoint: undefined } },
    });
  });
  // The vault notice is explicit: no credential field exists.
  expect(screen.getByTestId("cloud-credentials-vault-notice")).toHaveTextContent(/never transit the bridge/i);
  expect(screen.queryByLabelText(/password|api key/i)).not.toBeInTheDocument();
});

test("the dashboards tab mounts the D3 resources and spend views", async () => {
  const client = stubClient();
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);
  await screen.findByTestId("cloud-provider-card-gcd");

  fireEvent.click(screen.getByTestId("cloud-compute-tab-dashboards"));
  expect(await screen.findByTestId("cloud-jobs-spend")).toBeInTheDocument();
  expect(screen.getByTestId("cloud-jobs-resources")).toBeInTheDocument();
  expect(screen.getByText(/This month \$12\.50 · reserved \$4\.00/)).toBeInTheDocument();
});

const orphanResources = (): ResourcesResult => ({
  available: true,
  resources: [
    {
      provider: "gcd",
      kind: "instance",
      resource_id: "inst-1",
      region: "us-central1",
      job_id: "job-1",
      orphan: true,
    },
  ],
});

test("the dashboards tab terminates an orphan through the host client", async () => {
  const client = {
    ...stubClient(),
    cloudJobsResources: vi.fn(async (): Promise<ResourcesResult> => orphanResources()),
    cloudJobsTerminate: vi.fn(async (): Promise<TerminateResult> => ({
      accepted: true,
      resource_id: "inst-1",
      reason: "terminated inst-1",
    })),
  };
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);
  await screen.findByTestId("cloud-provider-card-gcd");

  fireEvent.click(screen.getByTestId("cloud-compute-tab-dashboards"));
  fireEvent.click(await screen.findByRole("button", { name: "Terminate" }));

  await waitFor(() => {
    expect(client.cloudJobsTerminate).toHaveBeenCalledWith("inst-1");
  });
  expect(await screen.findByTestId("cloud-jobs-terminate-notice")).toHaveTextContent("terminated inst-1");
});

test("the dashboards tab reports no daemon lease when terminate is missing", async () => {
  const client = {
    ...stubClient(),
    cloudJobsResources: vi.fn(async (): Promise<ResourcesResult> => orphanResources()),
  };
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);
  await screen.findByTestId("cloud-provider-card-gcd");

  fireEvent.click(screen.getByTestId("cloud-compute-tab-dashboards"));
  fireEvent.click(await screen.findByRole("button", { name: "Terminate" }));

  expect(await screen.findByTestId("cloud-jobs-terminate-notice")).toHaveTextContent("no daemon lease");
});

test("the request builder tab mounts the D4 builder when the client is attached", async () => {
  const client = stubClient();
  render(<CloudComputeSurface hostClient={client as never} onClose={() => {}} />);
  await screen.findByTestId("cloud-provider-card-gcd");

  fireEvent.click(screen.getByTestId("cloud-compute-tab-builder"));
  expect(screen.getByTestId("cloud-compute-builder")).toBeInTheDocument();

  // Without a client the tab explains instead of crashing.
  cleanup();
  render(<CloudComputeSurface hostClient={null} onClose={() => {}} />);
  fireEvent.click(screen.getByTestId("cloud-compute-tab-builder"));
  expect(screen.getByText(/Connect the bridge/i)).toBeInTheDocument();
});
