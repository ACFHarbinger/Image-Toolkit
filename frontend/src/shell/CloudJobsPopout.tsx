import { useState, type ReactElement } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { RunInCloudOffer, type CloudOffer } from "./RunInCloudOffer";

/** Gate D panel host. Logical role `cloud.jobs`; native window label `cloud-jobs`. */
export function CloudJobsPopout(): ReactElement {
  const [offer, setOffer] = useState<CloudOffer | null>(null);
  const [notice, setNotice] = useState("");

  const onPrefill = (owner: string, estimatedGb: number, deviceGb: number) => {
    const client = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-window",
      clientVersion: "1.0.0",
    });
    void client
      .cloudOfferPrefill({ owner, estimated_gb: estimatedGb, device_gb: deviceGb })
      .then((result) => {
        setOffer(result);
        setNotice(result.reason);
      })
      .catch(() => {
        setOffer(null);
        setNotice("cloud offer is unavailable");
      })
      .finally(() => {
        void client.close();
      });
  };

  return (
    <main data-testid="cloud-jobs-window" className="flex min-h-screen flex-col gap-4 p-6">
      <h1>Cloud Jobs</h1>
      <p>This labeled pop-out is ready for Gate D. The header badge stays on main.</p>
      <RunInCloudOffer offer={offer} notice={notice} onPrefill={onPrefill} />
    </main>
  );
}
