import React, { useEffect, useState } from "react";

export interface PrefsDescribeResult {
  readonly sections: readonly string[];
  readonly credentials_changed: false;
  readonly reason: string;
}

export interface PrefsClient {
  prefsDescribe(account: string): Promise<PrefsDescribeResult>;
}

const LOCKED = new Set(["credentials", "reset"]);

/** Settings window (#917). Credentials and reset never submit a password. */
export function SettingsWindow({
  hostClient,
  account,
  onClose,
}: {
  readonly hostClient: PrefsClient;
  readonly account: string;
  readonly onClose: () => void;
}): React.ReactElement {
  const [result, setResult] = useState<PrefsDescribeResult | null>(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState("");

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError("");
    hostClient.prefsDescribe(account).then(
      (next) => {
        if (cancelled) {
          return;
        }
        setResult(next);
        setActive((current) => (current && next.sections.includes(current) ? current : next.sections[0] ?? ""));
      },
      (exc: unknown) => {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "settings description failed");
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [hostClient, account]);

  const reason = result?.reason ?? "";
  const locked = LOCKED.has(active);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-window-title"
      data-testid="settings-window"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onClose();
        }
      }}
    >
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl border border-gray-200 bg-white text-gray-900 shadow-2xl dark:border-gray-700 dark:bg-gray-800 dark:text-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 id="settings-window-title" className="text-xl font-bold">
            Application Settings
          </h2>
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-2">
            Close
          </button>
        </div>
        {error ? (
          <p role="alert" className="px-6 py-4 text-red-600">
            {error}
          </p>
        ) : null}
        <div role="tablist" aria-label="Settings sections" className="flex flex-wrap border-b border-gray-200 dark:border-gray-700">
          {(result?.sections ?? []).map((section) => (
            <button
              key={section}
              type="button"
              role="tab"
              id={`settings-tab-${section}`}
              aria-selected={active === section}
              aria-controls={`settings-panel-${section}`}
              onClick={() => setActive(section)}
              className="px-4 py-3 font-medium"
            >
              {section}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {result && active ? (
            <section role="tabpanel" id={`settings-panel-${active}`} aria-labelledby={`settings-tab-${active}`}>
              <h3 className="text-sm font-semibold">{active}</h3>
              {locked ? <p>{reason}</p> : <p>This section does not change credentials.</p>}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
