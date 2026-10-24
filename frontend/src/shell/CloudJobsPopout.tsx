import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { CloudJobsWindow } from "./CloudJobsWindow";
import {
  ResourcesView,
  SpendView,
  type CloudResources,
  type CloudSpend,
} from "./CloudJobsViews";
import { useCloudBadge } from "./useCloudBadge";

const EMPTY_RESOURCES: CloudResources = { available: false, resources: [] };
const EMPTY_SPEND: CloudSpend = {
  available: false,
  month_actual_usd: 0,
  reserved_usd: 0,
  by_provider: [],
};
const POLL_MS = 15000;

/** Gate D pop-out. Logical role `cloud.jobs`; native window label `cloud-jobs`. */
export function CloudJobsPopout(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);
  const [resources, setResources] = useState<CloudResources>(EMPTY_RESOURCES);
  const [spend, setSpend] = useState<CloudSpend>(EMPTY_SPEND);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const next = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-window",
      clientVersion: "1.0.0",
    });
    setClient(next);
    let stop = false;
    const load = () => {
      void next
        .cloudJobsResources()
        .then((result) => {
          if (!stop) {
            setResources(result);
          }
        })
        .catch(() => {
          if (!stop) {
            setResources(EMPTY_RESOURCES);
          }
        });
      void next
        .cloudJobsSpend()
        .then((result) => {
          if (!stop) {
            setSpend(result);
          }
        })
        .catch(() => {
          if (!stop) {
            setSpend(EMPTY_SPEND);
          }
        });
    };
    load();
    void next.connect().catch(() => {});
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
      void next.close();
    };
  }, []);

  const badge = useCloudBadge(client);

  const onTerminate = (resourceId: string) => {
    if (!client) {
      setNotice("no daemon lease");
      return;
    }
    void client
      .cloudJobsTerminate(resourceId)
      .then((result) => {
        setNotice(result.reason);
      })
      .catch(() => {
        setNotice("no daemon lease");
      });
  };

  return (
    <CloudJobsWindow
      badge={badge}
      resources={<ResourcesView view={resources} notice={notice} onTerminate={onTerminate} />}
      spend={<SpendView view={spend} />}
    />
  );
}
