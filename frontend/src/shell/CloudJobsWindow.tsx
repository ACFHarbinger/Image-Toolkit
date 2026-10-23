import React from "react";

/** Labeled cloud.jobs shell. Later gates fill the panes. */
export function CloudJobsWindow({ badge }: { badge: string }): React.ReactElement {
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
    </main>
  );
}
