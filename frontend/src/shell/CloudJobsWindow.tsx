import React, { useEffect, useRef, useState } from "react";
import type { JobDetailResult, JobSummaryItem } from "../../../contracts/generated/ts";
import type { HostClient } from "../hostclient";
import { CloudJobsSettings } from "../views/cloudjobs/CloudJobsSettings";
import { JobDetail } from "./JobDetail";
import { JobsTable } from "./JobsTable";
import {
  ResourcesView,
  SpendView,
  type CloudResources,
  type CloudSpend,
} from "./CloudJobsViews";

const EMPTY_RESOURCES: CloudResources = { available: false, resources: [] };
const EMPTY_SPEND: CloudSpend = {
  available: false,
  month_actual_usd: 0,
  reserved_usd: 0,
  by_provider: [],
};
const RESOURCE_POLL_MS = 15000;

export interface CloudJobsWindowProps {
  readonly badge: string;
  readonly client?: HostClient | null;
  readonly hostClient?: HostClient | null;
  readonly resources?: React.ReactNode;
  readonly spend?: React.ReactNode;
  readonly offer?: React.ReactNode;
}

/** Labeled cloud.jobs shell with the jobs table, detail, resources, spend, settings, and the run-in-cloud offer. */
export function CloudJobsWindow({
  badge,
  client,
  hostClient,
  resources,
  spend,
  offer,
}: CloudJobsWindowProps): React.ReactElement {
  const activeClient = hostClient ?? client ?? null;
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
    if (!activeClient) {
      setJobs([]);
      setLoadingJobs(false);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await activeClient.cloudJobsList({
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
  }, [activeClient, filterState, filterProvider, searchQuery]);

  const detailGeneration = useRef(0);

  useEffect(() => {
    const generation = ++detailGeneration.current;
    const current = () => detailGeneration.current === generation;
    if (!activeClient || !selectedJobId) {
      setDetail(null);
      setLoadingDetail(false);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await activeClient.cloudJobsDetail({ job_id: selectedJobId });
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
  }, [activeClient, selectedJobId]);

  const [resourceView, setResourceView] = useState<CloudResources>(EMPTY_RESOURCES);
  const [spendView, setSpendView] = useState<CloudSpend>(EMPTY_SPEND);
  const [terminateNotice, setTerminateNotice] = useState("");

  useEffect(() => {
    if (!activeClient?.cloudJobsResources || !activeClient.cloudJobsSpend) {
      return;
    }
    let stop = false;
    const load = () => {
      void activeClient.cloudJobsResources().then((result) => {
        if (!stop) setResourceView(result);
      }).catch(() => {
        if (!stop) setResourceView(EMPTY_RESOURCES);
      });
      void activeClient.cloudJobsSpend().then((result) => {
        if (!stop) setSpendView(result);
      }).catch(() => {
        if (!stop) setSpendView(EMPTY_SPEND);
      });
    };
    load();
    const timer = window.setInterval(load, RESOURCE_POLL_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [activeClient]);

  const onTerminate = (resourceId: string) => {
    if (!activeClient?.cloudJobsTerminate) {
      setTerminateNotice("no daemon lease");
      return;
    }
    void activeClient.cloudJobsTerminate(resourceId).then((result) => {
      setTerminateNotice(result.reason);
    }).catch(() => {
      setTerminateNotice("no daemon lease");
    });
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
          cancelUnavailableReason="Cloud cancellation is unavailable until the authenticated cloud command path is connected."
        />
      </section>
      {resources ?? (
        <ResourcesView view={resourceView} notice={terminateNotice} onTerminate={onTerminate} />
      )}
      {spend ?? <SpendView view={spendView} />}
      {offer}
      <section data-testid="cloud-jobs-settings-section">
        <h2>Settings</h2>
        {activeClient ? (
          <CloudJobsSettings hostClient={activeClient} />
        ) : (
          <p data-testid="cloud-jobs-settings-status">Connecting to the bridge…</p>
        )}
      </section>
    </main>
  );
}
