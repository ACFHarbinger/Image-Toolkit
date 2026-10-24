import React from "react";
import type { HostClient } from "../hostclient";
import { CloudJobsSettings } from "../views/cloudjobs/CloudJobsSettings";

/** Labeled cloud.jobs shell. Later gates fill the panes. */
export function CloudJobsWindow({
  badge,
  hostClient = null,
}: {
  badge: string;
  hostClient?: HostClient | null;
}): React.ReactElement {
  return (
    <main data-testid="cloud-jobs-window" className="flex min-h-screen flex-col gap-4 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cloud Jobs</h1>
        <span data-testid="cloud-jobs-window-badge">{badge}</span>
      </header>
      <section data-testid="cloud-jobs-jobs">
        <h2>Jobs</h2>
      </section>
      <section data-testid="cloud-jobs-detail">
        <h2>Detail</h2>
      </section>
      <section data-testid="cloud-jobs-resources">
        <h2>Resources</h2>
      </section>
      <section data-testid="cloud-jobs-spend">
        <h2>Spend</h2>
      </section>
      <section data-testid="cloud-jobs-settings">
        <h2>Settings</h2>
        {hostClient ? (
          <CloudJobsSettings hostClient={hostClient} />
        ) : (
          <p data-testid="cloud-jobs-settings-status">Connecting to the bridge…</p>
        )}
      </section>
    </main>
  );
}
