import React from "react";

/** Gate D panel host. The native window is the labeled `cloud.jobs` pop-out. */
export function CloudJobsPopout(): React.ReactElement {
  return (
    <main className="flex min-h-screen flex-col gap-2 p-6">
      <h1>Cloud Jobs</h1>
      <p>This labeled pop-out is ready for Gate D. The header badge stays on main.</p>
    </main>
  );
}
