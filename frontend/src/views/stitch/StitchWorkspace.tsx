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

  const title = (route.startsWith("stitch.") ? route.slice("stitch.".length) : route).replace(/-/g, " ");

  return (
    <section
      data-testid="stitch-workspace"
      aria-label="Image Stitching"
      className="min-h-full bg-it-window-bg p-6 text-it-text"
    >
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        <header>
          <p className="text-xs font-semibold uppercase tracking-wide text-it-muted-text">Image Editor</p>
          <h2 className="text-lg font-semibold capitalize tracking-tight">{title}</h2>
          <p className="text-xs text-it-muted-text">{route}</p>
          {reason ? <p className="mt-1 text-sm">{reason}</p> : null}
        </header>
        <section
          aria-label="Shared canvas host"
          className="flex min-h-80 items-center justify-center rounded-2xl border border-dashed border-it-border bg-it-surface text-sm text-it-muted-text"
        >
          Shared canvas host
        </section>
      </div>
    </section>
  );
}
