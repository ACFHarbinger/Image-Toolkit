import React, { useEffect, useState } from "react";
import type { JobDetailResult, JobSummaryItem } from "../../../contracts/generated/ts";
import type { HostClient } from "../hostclient";
import { JobDetail } from "./JobDetail";
import { JobsTable } from "./JobsTable";

export interface CloudJobsWindowProps {
  readonly badge: string;
  readonly client?: HostClient | null;
}

/** Labeled cloud.jobs shell with Jobs table (D2) and Detail view (D2). */
export function CloudJobsWindow({ badge, client }: CloudJobsWindowProps): React.ReactElement {
  const [jobs, setJobs] = useState<JobSummaryItem[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [detail, setDetail] = useState<JobDetailResult | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const [filterState, setFilterState] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const refreshJobs = async () => {
    if (!client) return;
    setLoadingJobs(true);
    try {
      const res = await client.cloudJobsList({
        state: filterState || undefined,
        provider: filterProvider || undefined,
        search: searchQuery || undefined,
      });
      setJobs([...res.jobs]);
    } catch {
      setJobs([]);
    } finally {
      setLoadingJobs(false);
    }
  };

  const refreshDetail = async (id: string) => {
    if (!client) return;
    setLoadingDetail(true);
    try {
      const res = await client.cloudJobsDetail({ job_id: id });
      setDetail(res);
    } catch {
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    void refreshJobs();
  }, [client, filterState, filterProvider, searchQuery]);

  useEffect(() => {
    if (selectedJobId) {
      void refreshDetail(selectedJobId);
    } else {
      setDetail(null);
    }
  }, [client, selectedJobId]);

  const handleCancelJob = async (jobId: string) => {
    if (!client) return;
    setCancelling(true);
    try {
      await client.cancelJob(jobId);
      if (selectedJobId === jobId) {
        await refreshDetail(jobId);
      }
      await refreshJobs();
    } catch {
      // Ignored
    } finally {
      setCancelling(false);
    }
  };

  return (
    <main data-testid="cloud-jobs-window" className="flex min-h-screen flex-col gap-6 p-6">
      <header className="flex items-center justify-between border-b border-zinc-200 pb-3 dark:border-zinc-800">
        <h1 className="text-2xl font-semibold">Cloud Jobs</h1>
        <span data-testid="cloud-jobs-window-badge" className="rounded bg-zinc-100 px-2 py-1 text-sm font-medium dark:bg-zinc-800">
          {badge}
        </span>
      </header>

      <section data-testid="cloud-jobs-jobs" className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Jobs</h2>
        <JobsTable
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelectJob={(id) => setSelectedJobId(id)}
          filterState={filterState}
          onFilterStateChange={setFilterState}
          filterProvider={filterProvider}
          onFilterProviderChange={setFilterProvider}
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          loading={loadingJobs}
        />
      </section>

      <section data-testid="cloud-jobs-detail" className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Detail</h2>
        <JobDetail
          detail={detail}
          loading={loadingDetail}
          onCancel={handleCancelJob}
          cancelling={cancelling}
        />
      </section>

      <section data-testid="cloud-jobs-resources" className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Resources</h2>
      </section>

      <section data-testid="cloud-jobs-spend" className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Spend</h2>
      </section>
    </main>
  );
}
