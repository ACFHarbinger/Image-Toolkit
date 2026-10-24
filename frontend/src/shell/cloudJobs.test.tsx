import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { CloudComputeSurface } from "./CloudComputeSurface";
import { CloudJobsControl } from "./CloudJobsControl";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { formatCloudBadge } from "./cloudBadge";
import { JobDetail } from "./JobDetail";
import { JobsTable } from "./JobsTable";
import type { JobDetailResult, JobSummaryItem } from "../../../contracts/generated/ts";

afterEach(cleanup);

const MOCK_JOBS: JobSummaryItem[] = [
  {
    job_id: "job-101",
    kind: "batch",
    title: "Batch upscale 4x",
    state: "running",
    provider: "aws",
    created_at: 1729720000,
    started_at: 1729720005,
    ended_at: null,
    cost_usd: 1.25,
    shards_total: 4,
    shards_done: 2,
  },
  {
    job_id: "job-102",
    kind: "train",
    title: "LoRA fine-tuning",
    state: "completed",
    provider: "runpod",
    created_at: 1729710000,
    started_at: 1729710010,
    ended_at: 1729713600,
    cost_usd: 4.80,
    shards_total: 1,
    shards_done: 1,
  },
];

const MOCK_DETAIL: JobDetailResult = {
  job_id: "job-101",
  kind: "batch",
  title: "Batch upscale 4x",
  state: "running",
  provider: "aws",
  created_at: 1729720000,
  started_at: 1729720005,
  ended_at: null,
  events: [
    { id: 1, ts: 1729720000, type: "created", data: { shards: 4 } },
    { id: 2, ts: 1729720005, type: "state", data: { to: "running" } },
  ],
  outputs: ["/outputs/frame_001.png", "/outputs/frame_002.png"],
  logs: ["[info] worker started", "[info] processing shard 1"],
  metrics: {
    gpu_util_pct: 92.5,
    vram_used_mb: 18400,
    peak_vcpu: 7.8,
  },
  spend: {
    cost_so_far_usd: 1.25,
    reserved_usd: 3.50,
    max_spend_usd: 5.00,
  },
  daemon_status: {
    lease_owner: "daemon-pid-4122",
    wal_depth: 3,
    last_poll_ts: 1729720060,
  },
};

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

test("JobsTable renders rows and triggers selection and filters", () => {
  const onSelect = vi.fn();
  const onFilterState = vi.fn();
  const onFilterProvider = vi.fn();
  const onSearch = vi.fn();

  render(
    <JobsTable
      jobs={MOCK_JOBS}
      selectedJobId="job-101"
      onSelectJob={onSelect}
      filterState=""
      onFilterStateChange={onFilterState}
      filterProvider=""
      onFilterProviderChange={onFilterProvider}
      searchQuery=""
      onSearchQueryChange={onSearch}
    />
  );

  expect(screen.getByTestId("job-row-job-101")).toHaveTextContent("Batch upscale 4x");
  expect(screen.getByTestId("job-row-job-102")).toHaveTextContent("LoRA fine-tuning");

  fireEvent.click(screen.getByTestId("job-row-job-102"));
  expect(onSelect).toHaveBeenCalledWith("job-102");

  fireEvent.change(screen.getByTestId("jobs-state-filter"), { target: { value: "running" } });
  expect(onFilterState).toHaveBeenCalledWith("running");

  fireEvent.change(screen.getByTestId("jobs-search-input"), { target: { value: "upscale" } });
  expect(onSearch).toHaveBeenCalledWith("upscale");
});

test("JobDetail renders metrics, spend, timeline, logs, and daemon status", () => {
  const onCancel = vi.fn();
  render(<JobDetail detail={MOCK_DETAIL} onCancel={onCancel} />);

  expect(screen.getByTestId("job-detail-card")).toHaveTextContent("Batch upscale 4x");
  expect(screen.getByTestId("job-detail-metrics")).toHaveTextContent("92.5%");
  expect(screen.getByTestId("job-detail-metrics")).toHaveTextContent("18400 MB");
  expect(screen.getByTestId("job-detail-spend")).toHaveTextContent("$1.25");
  expect(screen.getByTestId("job-detail-spend")).toHaveTextContent("$3.50");
  expect(screen.getByTestId("job-detail-daemon")).toHaveTextContent("daemon-pid-4122");
  expect(screen.getByTestId("job-detail-timeline")).toHaveTextContent("running");
  expect(screen.getByTestId("job-detail-logs")).toHaveTextContent("[info] worker started");
  expect(screen.getByTestId("job-detail-outputs")).toHaveTextContent("/outputs/frame_001.png");

  fireEvent.click(screen.getByTestId("job-cancel-button"));
  expect(onCancel).toHaveBeenCalledWith("job-101");
});

test("CloudJobsWindow fetches jobs and detail from HostClient", async () => {
  const mockClient = {
    cloudJobsList: vi.fn().mockResolvedValue({ jobs: MOCK_JOBS }),
    cloudJobsDetail: vi.fn().mockResolvedValue(MOCK_DETAIL),
    cancelJob: vi.fn().mockResolvedValue({ ok: true }),
  };

  render(<CloudJobsWindow badge="1 · $1.25" client={mockClient as any} />);

  await waitFor(() => {
    expect(mockClient.cloudJobsList).toHaveBeenCalled();
    expect(screen.getByTestId("job-row-job-101")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("job-row-job-101"));

  await waitFor(() => {
    expect(mockClient.cloudJobsDetail).toHaveBeenCalledWith({ job_id: "job-101" });
    expect(screen.getByTestId("job-detail-card")).toBeInTheDocument();
  });
});

test("a late detail response does not replace the current selection", async () => {
  let resolveFirst: (value: typeof MOCK_DETAIL) => void = () => undefined;
  const first = new Promise<typeof MOCK_DETAIL>((resolve) => {
    resolveFirst = resolve;
  });
  const secondDetail = { ...MOCK_DETAIL, job_id: "job-102", title: "Second job" };
  const mockClient = {
    cloudJobsList: vi.fn().mockResolvedValue({ jobs: MOCK_JOBS }),
    cloudJobsDetail: vi.fn((params: { job_id: string }) =>
      params.job_id === "job-101" ? first : Promise.resolve(secondDetail),
    ),
    cancelJob: vi.fn(),
  };

  render(<CloudJobsWindow badge="—" client={mockClient as never} />);
  await screen.findByTestId("job-row-job-101");
  fireEvent.click(screen.getByTestId("job-row-job-101"));
  fireEvent.click(await screen.findByTestId("job-row-job-102"));
  await waitFor(() => {
    expect(screen.getByTestId("job-detail-card")).toHaveTextContent("Second job");
  });
  resolveFirst({ ...MOCK_DETAIL, title: "Stale first job" });
  await waitFor(() => {
    expect(screen.getByTestId("job-detail-card")).toHaveTextContent("Second job");
  });
  expect(screen.getByTestId("job-detail-card")).not.toHaveTextContent("Stale first job");
});


test("cloud jobs never call the unrelated in-memory cancellation route", async () => {
  const client = { cloudJobsList: vi.fn().mockResolvedValue({ jobs: MOCK_JOBS }),
    cloudJobsDetail: vi.fn().mockResolvedValue(MOCK_DETAIL), cancelJob: vi.fn() };
  render(<CloudJobsWindow badge="—" client={client as never} />);
  fireEvent.click(await screen.findByTestId("job-row-job-101"));
  const button = await screen.findByTestId("job-cancel-button");
  expect(button).toBeDisabled();
  expect(screen.getByTestId("cloud-cancel-unavailable")).toHaveTextContent("unavailable");
  fireEvent.click(button);
  expect(client.cancelJob).not.toHaveBeenCalled();
});
