import React from "react";
import type { JobDetailResult } from "../../../contracts/generated/ts";

export interface JobDetailProps {
  readonly detail: JobDetailResult | null;
  readonly loading?: boolean;
  readonly onCancel?: (jobId: string) => void;
  readonly cancelling?: boolean;
  readonly cancelUnavailableReason?: string;
}

const ACTIVE_STATES = new Set(["queued", "provisioning", "running"]);

export function JobDetail({
  detail,
  loading = false,
  onCancel,
  cancelling = false,
  cancelUnavailableReason,
}: JobDetailProps): React.ReactElement {
  if (loading) {
    return (
      <div data-testid="job-detail-loading" className="rounded border border-zinc-200 p-6 text-center text-sm text-zinc-500 dark:border-zinc-800">
        Loading job detail...
      </div>
    );
  }

  if (!detail) {
    return (
      <div data-testid="job-detail-empty" className="rounded border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500 dark:border-zinc-700">
        Select a job from the table to view timeline, logs, metrics, and spend.
      </div>
    );
  }

  const canCancel = ACTIVE_STATES.has(detail.state);

  return (
    <div data-testid="job-detail-card" className="flex flex-col gap-5 rounded border border-zinc-200 p-5 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">{detail.title || detail.job_id}</h3>
            <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-medium uppercase dark:bg-zinc-800">
              {detail.state}
            </span>
          </div>
          <p className="font-mono text-xs text-zinc-500">
            {detail.job_id} • {detail.provider.toUpperCase()} • {detail.kind}
          </p>
        </div>

        {canCancel && (onCancel || cancelUnavailableReason) && (
          <button
            data-testid="job-cancel-button"
            type="button"
            disabled={cancelling || !onCancel || Boolean(cancelUnavailableReason)}
            title={cancelUnavailableReason}
            onClick={() => onCancel?.(detail.job_id)}
            className="rounded bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {cancelling ? "Cancelling..." : "Cancel Job"}
          </button>
        )}
      </div>

      {canCancel && cancelUnavailableReason && (
        <p role="status" data-testid="cloud-cancel-unavailable">{cancelUnavailableReason}</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div data-testid="job-detail-metrics" className="rounded bg-zinc-50 p-3 dark:bg-zinc-900">
          <h4 className="text-xs font-semibold uppercase text-zinc-500">Metrics</h4>
          <div className="mt-2 space-y-1 text-sm">
            <div>GPU: <span className="font-mono font-medium">{detail.metrics.gpu_util_pct}%</span></div>
            <div>VRAM: <span className="font-mono font-medium">{detail.metrics.vram_used_mb} MB</span></div>
            <div>vCPU: <span className="font-mono font-medium">{detail.metrics.peak_vcpu}</span></div>
          </div>
        </div>

        <div data-testid="job-detail-spend" className="rounded bg-zinc-50 p-3 dark:bg-zinc-900">
          <h4 className="text-xs font-semibold uppercase text-zinc-500">Spend</h4>
          <div className="mt-2 space-y-1 text-sm">
            <div>Spent: <span className="font-mono font-medium">${detail.spend.cost_so_far_usd.toFixed(2)}</span></div>
            <div>Reserved: <span className="font-mono font-medium">${detail.spend.reserved_usd.toFixed(2)}</span></div>
            <div>Cap: <span className="font-mono font-medium">${detail.spend.max_spend_usd.toFixed(2)}</span></div>
          </div>
        </div>

        <div data-testid="job-detail-daemon" className="rounded bg-zinc-50 p-3 dark:bg-zinc-900">
          <h4 className="text-xs font-semibold uppercase text-zinc-500">Daemon Status</h4>
          <div className="mt-2 space-y-1 text-sm">
            <div>Lease: <span className="font-mono font-medium">{detail.daemon_status.lease_owner}</span></div>
            <div>WAL Depth: <span className="font-mono font-medium">{detail.daemon_status.wal_depth}</span></div>
            <div>
              Poll:{" "}
              <span className="font-mono text-xs">
                {detail.daemon_status.last_poll_ts ? new Date(detail.daemon_status.last_poll_ts * 1000).toLocaleTimeString() : "—"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div data-testid="job-detail-timeline">
        <h4 className="text-xs font-semibold uppercase text-zinc-500">Timeline</h4>
        <div className="mt-2 max-h-40 overflow-y-auto rounded border border-zinc-200 p-2 text-xs dark:border-zinc-800">
          {detail.events.length === 0 ? (
            <p className="text-zinc-500">No events recorded.</p>
          ) : (
            <ul className="space-y-1.5">
              {detail.events.map((ev) => (
                <li key={ev.id} className="flex items-center gap-2 font-mono">
                  <span className="text-zinc-400">{new Date(ev.ts * 1000).toLocaleTimeString()}</span>
                  <span className="font-semibold text-blue-600 dark:text-blue-400">{ev.type}</span>
                  <span className="truncate text-zinc-600 dark:text-zinc-300">{JSON.stringify(ev.data)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div data-testid="job-detail-logs">
        <h4 className="text-xs font-semibold uppercase text-zinc-500">Live Log</h4>
        <div className="mt-2 max-h-36 overflow-y-auto rounded bg-zinc-900 p-3 font-mono text-xs text-zinc-100">
          {detail.logs.length === 0 ? (
            <span className="text-zinc-500">No log output yet.</span>
          ) : (
            detail.logs.map((line, idx) => <div key={idx}>{line}</div>)
          )}
        </div>
      </div>

      <div data-testid="job-detail-outputs">
        <h4 className="text-xs font-semibold uppercase text-zinc-500">Outputs</h4>
        <div className="mt-2 text-xs">
          {detail.outputs.length === 0 ? (
            <span className="text-zinc-500">No outputs produced yet.</span>
          ) : (
            <ul className="list-inside list-disc space-y-1 font-mono">
              {detail.outputs.map((out, idx) => (
                <li key={idx} className="truncate">{out}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
