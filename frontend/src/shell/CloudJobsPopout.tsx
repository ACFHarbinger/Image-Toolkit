import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { useCloudBadge } from "./useCloudBadge";

/** Gate D pop-out. Logical role `cloud.jobs`; native window label `cloud-jobs`. */
export function CloudJobsPopout(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);
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
  return <CloudJobsWindow badge={badge} hostClient={client} />;
}
