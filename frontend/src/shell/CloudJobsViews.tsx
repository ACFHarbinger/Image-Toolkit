import type { ReactElement } from "react";

export interface CloudResourceRow {
  provider: string;
  kind: string;
  resource_id: string;
  region: string;
  job_id: string;
  orphan: boolean;
}

export interface CloudResources {
  available: boolean;
  resources: CloudResourceRow[];
}

export interface CloudSpend {
  available: boolean;
  month_actual_usd: number;
  reserved_usd: number;
  by_provider: { provider: string; actual_usd: number }[];
}

export function money(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

export function ResourcesView({
  view,
  notice,
  onTerminate,
}: {
  view: CloudResources;
  notice: string;
  onTerminate: (resourceId: string) => void;
}): ReactElement {
  return (
    <section data-testid="cloud-jobs-resources" className="flex flex-col gap-2">
      <h2>Resources</h2>
      {!view.available ? <p>Resources unavailable</p> : null}
      {view.available && view.resources.length === 0 ? <p>No tagged resources</p> : null}
      <ul>
        {view.resources.map((row) => (
          <li key={row.resource_id}>
            <span>
              {row.provider} {row.kind} {row.resource_id}
              {row.orphan ? " orphan" : ""}
            </span>
            {row.orphan ? (
              <button type="button" onClick={() => onTerminate(row.resource_id)}>
                Terminate
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {notice ? <p data-testid="cloud-jobs-terminate-notice">{notice}</p> : null}
    </section>
  );
}

export function SpendView({ view }: { view: CloudSpend }): ReactElement {
  return (
    <section data-testid="cloud-jobs-spend" className="flex flex-col gap-2">
      <h2>Spend</h2>
      {!view.available ? <p>Spend unavailable</p> : null}
      {view.available ? (
        <>
          <p data-testid="cloud-jobs-month-spend">
            This month {money(view.month_actual_usd)} · reserved {money(view.reserved_usd)}
          </p>
          <ul>
            {view.by_provider.map((row) => (
              <li key={row.provider}>
                {row.provider} {money(row.actual_usd)}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
