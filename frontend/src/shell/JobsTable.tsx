import React from "react";
import type { JobSummaryItem } from "../../../contracts/generated/ts";

export interface JobsTableProps {
  readonly jobs: readonly JobSummaryItem[];
  readonly selectedJobId: string | null;
  readonly onSelectJob: (jobId: string) => void;
  readonly filterState: string;
  readonly onFilterStateChange: (state: string) => void;
  readonly filterProvider: string;
  readonly onFilterProviderChange: (provider: string) => void;
  readonly searchQuery: string;
  readonly onSearchQueryChange: (query: string) => void;
  readonly loading?: boolean;
}

const STATE_COLORS: Record<string, string> = {
  queued: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  provisioning: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  running: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  failed: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
  cancelled: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300",
};

export function JobsTable({
  jobs,
  selectedJobId,
  onSelectJob,
  filterState,
  onFilterStateChange,
  filterProvider,
  onFilterProviderChange,
  searchQuery,
  onSearchQueryChange,
  loading = false,
}: JobsTableProps): React.ReactElement {
  return (
    <div data-testid="jobs-table-container" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <input
          data-testid="jobs-search-input"
          type="text"
          placeholder="Search jobs..."
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
        <select
          data-testid="jobs-state-filter"
          value={filterState}
          onChange={(e) => onFilterStateChange(e.target.value)}
          className="rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="">All States</option>
          <option value="queued">Queued</option>
          <option value="provisioning">Provisioning</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          data-testid="jobs-provider-filter"
          value={filterProvider}
          onChange={(e) => onFilterProviderChange(e.target.value)}
          className="rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="">All Providers</option>
          <option value="aws">AWS</option>
          <option value="gcp">GCP</option>
          <option value="azure">Azure</option>
          <option value="runpod">RunPod</option>
        </select>
        {loading && <span className="text-xs text-zinc-500">Loading...</span>}
      </div>

      <div className="overflow-x-auto rounded border border-zinc-200 dark:border-zinc-800">
        <table data-testid="jobs-table" className="w-full text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-xs font-semibold uppercase text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-2">Job ID</th>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">Kind</th>
              <th className="px-4 py-2">Provider</th>
              <th className="px-4 py-2">State</th>
              <th className="px-4 py-2">Shards</th>
              <th className="px-4 py-2">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                  {loading ? "Loading jobs..." : "No jobs found"}
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const isSelected = job.job_id === selectedJobId;
                const badgeClass = STATE_COLORS[job.state] ?? "bg-zinc-100 text-zinc-800";
                return (
                  <tr
                    key={job.job_id}
                    data-testid={`job-row-${job.job_id}`}
                    onClick={() => onSelectJob(job.job_id)}
                    className={`cursor-pointer transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50 ${
                      isSelected ? "bg-blue-50 font-medium dark:bg-blue-950/40" : ""
                    }`}
                  >
                    <td className="px-4 py-2 font-mono text-xs">{job.job_id}</td>
                    <td className="px-4 py-2">{job.title || "—"}</td>
                    <td className="px-4 py-2 capitalize">{job.kind}</td>
                    <td className="px-4 py-2 uppercase">{job.provider}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${badgeClass}`}>
                        {job.state}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {job.shards_done} / {job.shards_total}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">${job.cost_usd.toFixed(2)}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
