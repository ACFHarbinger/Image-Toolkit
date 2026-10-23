import { useEffect, useState, type ReactElement } from "react";
import { HostClient, RustTransport } from "../hostclient";
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
const POLL_MS = 15000;

/** Gate D resources and spend. Logical role `cloud.jobs`. */
export function CloudJobsPopout(): ReactElement {
  const [resources, setResources] = useState<CloudResources>(EMPTY_RESOURCES);
  const [spend, setSpend] = useState<CloudSpend>(EMPTY_SPEND);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const client = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-window",
      clientVersion: "1.0.0",
    });
    let stop = false;
    const load = () => {
      void client
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
      void client
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
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
      void client.close();
    };
  }, []);

  const onTerminate = (resourceId: string) => {
    const client = new HostClient(new RustTransport(), {
      clientName: "cloud-jobs-window",
      clientVersion: "1.0.0",
    });
    void client
      .cloudJobsTerminate(resourceId)
      .then((result) => {
        setNotice(result.reason);
      })
      .catch(() => {
        setNotice("no daemon lease");
      })
      .finally(() => {
        void client.close();
      });
  };

  return (
    <main data-testid="cloud-jobs-window" className="flex min-h-screen flex-col gap-4 p-6">
      <h1>Cloud Jobs</h1>
      <ResourcesView view={resources} notice={notice} onTerminate={onTerminate} />
      <SpendView view={spend} />
    </main>
  );
}
