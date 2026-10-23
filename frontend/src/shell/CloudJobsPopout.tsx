import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { CloudJobsSettings } from "../views/cloudjobs/CloudJobsSettings";

/** Gate D panel host. Logical role `cloud.jobs`; native window label `cloud-jobs`.
 * Owns its bridge client like the main shell: connect on mount, close on unmount. */
export function CloudJobsPopout(): React.ReactElement {
  const [hostClient, setHostClient] = useState<HostClient | null>(null);

  useEffect(() => {
    const client = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-popout",
      clientVersion: "1.0.0",
    });
    setHostClient(client);
    void client.connect().catch(() => {});
    return () => {
      void client.close();
    };
  }, []);

  if (!hostClient) {
    return (
      <main className="flex min-h-screen flex-col gap-2 p-6">
        <h1>Cloud Jobs</h1>
        <p>Connecting to the bridge…</p>
      </main>
    );
  }
  return <CloudJobsSettings hostClient={hostClient} />;
}
