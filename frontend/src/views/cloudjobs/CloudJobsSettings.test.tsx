import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { GetResult, SetResult } from "../../../../contracts/generated/ts";
import { CloudJobsSettings } from "./CloudJobsSettings";
import { CLOUD_JOBS_SETTINGS_KEY, type CloudJobsSettingsDocument } from "./cloudSettings";

expect.extend(matchers);

afterEach(() => cleanup());

function documentFixture(overrides: Partial<CloudJobsSettingsDocument> = {}): CloudJobsSettingsDocument {
  return {
    estimates_enabled: true,
    warnings_enabled: true,
    hard_caps_enabled: true,
    default_max_runtime_s: 21600,
    default_max_spend_usd: 10,
    monthly_cap_usd: 100,
    warn_job_spend_usd: 5,
    warn_runtime_s: 10800,
    warn_egress_gb: 20,
    warn_price_age_days: 30,
    warn_cap_fraction: 0.8,
    max_concurrent_jobs: 4,
    max_concurrent_gpu_instances: 2,
    max_reserved_usd: 50,
    max_attempts: 3,
    fallback_enabled: false,
    default_regions: { gcp: "us-central1" },
    sensitive_allowlist: ["gcp"],
    packing_mode: "one_to_one",
    share_cache_volumes: true,
    history_retention_days: 90,
    staged_input_ttl_days: 0,
    cache_ttl_days: 30,
    cache_budget_gb: 200,
    output_retention_days: 14,
    notify_desktop: true,
    notify_webhook_url: "",
    notify_email: "",
    ...overrides,
  };
}

function stubClient() {
  return {
    getSetting: vi.fn(async (): Promise<GetResult> => ({
      key: CLOUD_JOBS_SETTINGS_KEY,
      value: documentFixture() as unknown as GetResult["value"],
      scope: "account" as const,
    })),
    setSetting: vi.fn(
      async (_params: { key: string; value: unknown }): Promise<SetResult> => ({
        key: CLOUD_JOBS_SETTINGS_KEY,
        value: documentFixture() as unknown as SetResult["value"],
        scope: "account" as const,
      }),
    ),
  };
}

test("loads the document over settings.get and renders the D5 sections", async () => {
  const client = stubClient();
  render(<CloudJobsSettings hostClient={client as never} />);

  expect(await screen.findByTestId("cloud-jobs-settings")).toBeInTheDocument();
  expect(client.getSetting).toHaveBeenCalledWith({ key: CLOUD_JOBS_SETTINGS_KEY });
  for (const section of ["safeguards", "caps", "thresholds", "admission", "recovery", "instances", "retention", "notifications", "placement"]) {
    expect(screen.getByTestId(`cloud-jobs-section-${section}`)).toBeInTheDocument();
  }
  expect((screen.getByTestId("setting-monthly_cap_usd") as HTMLInputElement).value).toBe("100");
  expect((screen.getByTestId("setting-fallback_enabled") as HTMLInputElement).checked).toBe(false);
  expect((screen.getByTestId("setting-notify_webhook_url") as HTMLInputElement).value).toBe("");
});

test("an edit and Save writes the whole document through settings.set", async () => {
  const client = stubClient();
  client.setSetting.mockImplementation(async (_params) => ({
    key: CLOUD_JOBS_SETTINGS_KEY,
    value: documentFixture({ monthly_cap_usd: 250 }) as unknown as SetResult["value"],
    scope: "account",
  }));
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");

  fireEvent.change(screen.getByTestId("setting-monthly_cap_usd"), { target: { value: "250" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(client.setSetting).toHaveBeenCalledTimes(1);
  });
  const params = client.setSetting.mock.calls[0][0] as unknown as { key: string; value: CloudJobsSettingsDocument };
  expect(params.key).toBe(CLOUD_JOBS_SETTINGS_KEY);
  expect(params.value.monthly_cap_usd).toBe(250);
  // Untouched fields ride along: the document saves whole.
  expect(params.value.packing_mode).toBe("one_to_one");
});

test("a rejected save surfaces the error without losing the form", async () => {
  const client = stubClient();
  client.setSetting.mockRejectedValue(new Error("packing_mode must be one of PACKING_MODES"));
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");

  fireEvent.change(screen.getByTestId("setting-packing_mode"), { target: { value: "parallel" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(/packing_mode/i);
  // The edited value is still on screen, not reset by the failure.
  expect((screen.getByTestId("setting-packing_mode") as HTMLSelectElement).value).toBe("parallel");
});

test("the regions editor edits, adds and removes provider rows", async () => {
  const client = stubClient();
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");

  fireEvent.change(screen.getByLabelText("region for gcp"), { target: { value: "europe-west1" } });
  fireEvent.click(screen.getByRole("button", { name: "Add region" }));
  const providerInputs = screen.getAllByLabelText(/region provider/);
  expect(providerInputs).toHaveLength(2);

  // Name the new provider row and give it a region.
  fireEvent.change(providerInputs[1], { target: { value: "aws" } });
  fireEvent.change(screen.getByLabelText("region for aws"), { target: { value: "us-east-1" } });

  fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
  expect(screen.queryByLabelText("region for aws")).not.toBeInTheDocument();
  expect(screen.getByLabelText("region for gcp")).toBeInTheDocument();
});

test("an initial load failure is visible and can be retried", async () => {
  const client = stubClient();
  client.getSetting.mockRejectedValueOnce(new Error("sidecar unavailable"));
  render(<CloudJobsSettings hostClient={client as never} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("sidecar unavailable");
  expect(screen.queryByTestId("cloud-jobs-settings-status")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByTestId("cloud-jobs-settings")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(client.getSetting).toHaveBeenCalledTimes(2);
});

test.each([null, {}, { packing_mode: "one_to_one" }])(
  "a malformed initial document (%j) reports an error and recovers on retry",
  async (value) => {
    const client = stubClient();
    client.getSetting.mockResolvedValueOnce({
      key: CLOUD_JOBS_SETTINGS_KEY, value: value as GetResult["value"], scope: "account",
    });
    render(<CloudJobsSettings hostClient={client as never} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("malformed");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("cloud-jobs-settings")).toBeInTheDocument();
    expect(client.setSetting).not.toHaveBeenCalled();
  },
);


test("provider editing keeps row identity and focus across keystrokes", async () => {
  const client = stubClient();
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");
  fireEvent.click(screen.getByRole("button", { name: "Add region" }));
  const input = screen.getAllByLabelText(/^region provider/)[1];
  input.focus();
  for (const value of ["a", "aw", "aws"]) {
    fireEvent.change(input, { target: { value } });
    expect(screen.getByLabelText(`region provider ${value}`)).toBe(input);
    expect(document.activeElement).toBe(input);
  }
});

test("duplicate provider drafts cannot overwrite another region or be saved", async () => {
  const client = stubClient();
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");
  fireEvent.click(screen.getByRole("button", { name: "Add region" }));
  fireEvent.change(screen.getAllByLabelText(/^region provider/)[1], { target: { value: "GCP" } });
  expect(screen.getByRole("alert")).toHaveTextContent("unique");
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(client.setSetting).not.toHaveBeenCalled();
  expect(screen.getByLabelText("region for gcp")).toHaveValue("us-central1");
  fireEvent.change(screen.getByLabelText("region provider GCP"), { target: { value: "aws" } });
  fireEvent.change(screen.getByLabelText("region for aws"), { target: { value: "us-east-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(client.setSetting).toHaveBeenCalledTimes(1));
  expect((client.setSetting.mock.calls[0][0].value as CloudJobsSettingsDocument).default_regions)
    .toEqual({ gcp: "us-central1", aws: "us-east-1" });
});

test("a trailing comma stays in the provider allowlist until blur or save", async () => {
  const client = stubClient();
  client.setSetting.mockImplementation(async (params) => ({
    key: CLOUD_JOBS_SETTINGS_KEY,
    value: params.value as SetResult["value"],
    scope: "account",
  }));
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");

  const allowlist = screen.getByTestId("setting-sensitive_allowlist");
  fireEvent.change(allowlist, { target: { value: "gcp," } });
  expect(allowlist).toHaveValue("gcp,");
  fireEvent.change(allowlist, { target: { value: "gcp, aws" } });
  expect(allowlist).toHaveValue("gcp, aws");
  fireEvent.blur(allowlist);
  expect(allowlist).toHaveValue("gcp, aws");

  fireEvent.change(allowlist, { target: { value: "gcp, aws," } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(client.setSetting).toHaveBeenCalledTimes(1));
  expect((client.setSetting.mock.calls[0][0].value as CloudJobsSettingsDocument).sensitive_allowlist)
    .toEqual(["gcp", "aws"]);
});

test("settings inputs stay disabled while a save is pending", async () => {
  const client = stubClient();
  let release: (value: SetResult) => void = () => undefined;
  client.setSetting.mockImplementation(() => new Promise<SetResult>((resolve) => {
    release = resolve;
  }));
  render(<CloudJobsSettings hostClient={client as never} />);
  await screen.findByTestId("cloud-jobs-settings");

  fireEvent.change(screen.getByTestId("setting-monthly_cap_usd"), { target: { value: "250" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled());
  expect(screen.getByTestId("setting-monthly_cap_usd")).toBeDisabled();
  expect(screen.getByTestId("setting-sensitive_allowlist")).toBeDisabled();
  expect(screen.getByTestId("setting-packing_mode")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Add region" })).toBeDisabled();
  fireEvent.change(screen.getByTestId("setting-monthly_cap_usd"), { target: { value: "999" } });
  expect(screen.getByTestId("setting-monthly_cap_usd")).toHaveValue(250);

  release({
    key: CLOUD_JOBS_SETTINGS_KEY,
    value: documentFixture({ monthly_cap_usd: 250 }) as unknown as SetResult["value"],
    scope: "account",
  });
  await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled());
  expect(screen.getByTestId("setting-monthly_cap_usd")).toHaveValue(250);
  expect(screen.getByTestId("setting-monthly_cap_usd")).toBeEnabled();
});
