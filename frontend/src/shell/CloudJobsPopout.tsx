import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { RequestBuilder } from "../views/cloudjobs/RequestBuilder";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { useCloudBadge } from "./useCloudBadge";

export type CloudJobsTab = "builder" | "jobs";

/** Gate D panel host (#847, #850). Logical role `cloud.jobs`; native window label `cloud-jobs`. */
export function CloudJobsPopout(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);
  const [activeTab, setActiveTab] = useState<CloudJobsTab>("builder");

  useEffect(() => {
    const next = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-window",
      clientVersion: "1.0.0",
    });
    setClient(next);
    void next.connect().catch(() => {});
    return () => {
      void next.close();
    };
  }, []);

  const badge = useCloudBadge(client);

  return (
    <main data-testid="cloud-jobs-popout" className="flex min-h-screen flex-col bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      {/* Popout Header Navigation */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center gap-3">
          <span className="text-xl">☁️</span>
          <div>
            <h1 className="text-lg font-bold">Cloud Jobs Workspace</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Gate D Submit Surfaces & Orchestration</p>
          </div>
        </div>
        <nav className="flex items-center gap-2">
          <button
            type="button"
            data-testid="tab-request-builder"
            onClick={() => setActiveTab("builder")}
            className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition-colors ${
              activeTab === "builder"
                ? "bg-indigo-600 text-white shadow"
                : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            }`}
          >
            Request Builder
          </button>
          <button
            type="button"
            data-testid="tab-jobs-queue"
            onClick={() => setActiveTab("jobs")}
            className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition-colors ${
              activeTab === "jobs"
                ? "bg-indigo-600 text-white shadow"
                : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            }`}
          >
            Jobs & Queue
          </button>
        </nav>
      </header>

      {/* Main Tab Content */}
      <div className="flex-1 p-6">
        {activeTab === "builder" && (
          <RequestBuilder client={client} />
        )}
        {activeTab === "jobs" && (
          <div data-testid="cloud-jobs-queue-view">
            <CloudJobsWindow badge={badge} />
          </div>
        )}
      </div>
    </main>
  );
}
