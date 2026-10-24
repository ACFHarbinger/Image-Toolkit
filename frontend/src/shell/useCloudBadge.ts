import { useEffect, useState } from "react";
import type { HostClient } from "../hostclient";
import { formatCloudBadge } from "./cloudBadge";

const POLL_MS = 15000;

export function useCloudBadge(client: HostClient | null): string {
  const [badge, setBadge] = useState("—");
  useEffect(() => {
    if (!client) {
      return;
    }
    let cancelled = false;
    const load = () => {
      void client
        .cloudJobsSummary()
        .then((summary) => {
          if (!cancelled) {
            setBadge(formatCloudBadge(summary));
          }
        })
        .catch(() => {
          if (!cancelled) {
            setBadge("—");
          }
        });
    };
    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [client]);
  return badge;
}
