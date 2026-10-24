import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { RunInCloudOffer, type CloudOffer } from "./RunInCloudOffer";
import { useCloudBadge } from "./useCloudBadge";

/** Gate D pop-out. Logical role `cloud.jobs`; native window label `cloud-jobs`. */
export function CloudJobsPopout(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);
  const [offer, setOffer] = useState<CloudOffer | null>(null);
  const [notice, setNotice] = useState("");

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

  const onPrefill = (owner: string, estimatedGb: number, deviceGb: number) => {
    if (!client) {
      setOffer(null);
      setNotice("cloud offer is unavailable");
      return;
    }
    void client
      .cloudOfferPrefill({ owner, estimated_gb: estimatedGb, device_gb: deviceGb })
      .then((result) => {
        setOffer(result);
        setNotice(result.reason);
      })
      .catch(() => {
        setOffer(null);
        setNotice("cloud offer is unavailable");
      });
  };

  return (
    <CloudJobsWindow
      badge={badge}
      offer={<RunInCloudOffer offer={offer} notice={notice} onPrefill={onPrefill} />}
    />
  );
}
