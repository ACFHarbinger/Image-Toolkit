import React, { useEffect, useRef, useState } from "react";
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

  const [filterState, setFilterState] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const listGeneration = useRef(0);

  useEffect(() => {
    const generation = ++listGeneration.current;
    const current = () => listGeneration.current === generation;
    if (!client) {
      setJobs([]);
      setLoadingJobs(false);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await client.cloudJobsList({
          state: filterState || undefined,
          provider: filterProvider || undefined,
          search: searchQuery || undefined,
        });
        if (current()) setJobs([...result.jobs]);
      } catch {
        if (current()) setJobs([]);
      } finally {
        if (current()) {
          setLoadingJobs(false);
          timer = setTimeout(() => void refresh(), 2000);
        }
      }
    };
    setLoadingJobs(true);
    void refresh();
    return () => {
      listGeneration.current += 1;
      clearTimeout(timer);
    };
  }, [client, filterState, filterProvider, searchQuery]);

  const detailGeneration = useRef(0);

  useEffect(() => {
    const generation = ++detailGeneration.current;
    const current = () => detailGeneration.current === generation;
    if (!client || !selectedJobId) {
      setDetail(null);
      setLoadingDetail(false);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await client.cloudJobsDetail({ job_id: selectedJobId });
        if (current()) setDetail(result);
      } catch {
        if (current()) setDetail(null);
      } finally {
        if (current()) {
          setLoadingDetail(false);
          timer = setTimeout(() => void refresh(), 2000);
        }
      }
    };
    setLoadingDetail(true);
    void refresh();
    return () => {
      detailGeneration.current += 1;
      clearTimeout(timer);
    };
  }, [client, selectedJobId]);


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
          cancelUnavailableReason="Cloud cancellation is unavailable until the authenticated cloud command path is connected."
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
