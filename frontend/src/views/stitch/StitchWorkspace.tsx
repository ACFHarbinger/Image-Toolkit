import React, { useEffect, useState } from "react";

export interface StitchStatusResult {
  readonly route: string;
  readonly started: false;
  readonly reason: string;
}

export interface StitchClient {
  stitchStatus(route: string): Promise<StitchStatusResult>;
}

/** Eight catalog routes, one workspace (#914). The stitch pipeline stays stopped. */
export function StitchWorkspace({
  route,
  hostClient,
}: {
  readonly route: string;
  readonly hostClient: StitchClient;
}): React.ReactElement {
  const [reason, setReason] = useState("");

  useEffect(() => {
    let cancelled = false;
    setReason("");
    hostClient
      .stitchStatus(route)
      .then((result) => {
        if (!cancelled) {
          setReason(result.reason);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setReason("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hostClient, route]);

  return (
    <section data-testid="stitch-workspace" aria-label="Image Stitching">
      <h2>{route}</h2>
      {reason ? <p>{reason}</p> : null}
      <section aria-label="Shared canvas host">Shared canvas host</section>
    </section>
  );
}
