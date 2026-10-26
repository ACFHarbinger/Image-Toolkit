// Entity reconnaissance and provenance (B-06 / #911): the HostClient-driven
// view for `web.entity-recon` — the page had no webview until now. The
// recon engine (dataset index, and the web dispatcher behind an explicit
// scope) is attached on the sidecar; with none attached the results stay
// `available: false` and the view says so instead of inventing an
// identity. Web discovery runs only at the user's explicit request.

import React, { useEffect, useState } from "react";
import type { EntityReconDescribeResult, EntityReconResolveResult } from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";

export interface EntityReconViewProps {
  hostClient: HostClient;
}

type Scope = "local" | "web" | "both";

export function EntityReconView({ hostClient }: EntityReconViewProps) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [defaultScope, setDefaultScope] = useState<Scope>("local");
  const [scope, setScope] = useState<Scope>("local");
  const [threshold, setThreshold] = useState<number>(0.55);
  const [topK, setTopK] = useState<number>(5);
  const [imagePath, setImagePath] = useState("");
  const [result, setResult] = useState<EntityReconResolveResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const described: EntityReconDescribeResult = await hostClient.entityReconDescribe();
        if (cancelled) return;
        setAvailable(described.available);
        setDefaultScope(described.config.search_scope);
        setScope(described.config.search_scope);
        setThreshold(described.config.local_match_threshold);
        setTopK(described.config.top_k);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [hostClient]);

  const resolve = async () => {
    if (!imagePath.trim()) {
      setError("Pick a cutout image first.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const resolved = await hostClient.entityReconResolve({
        image_path: imagePath.trim(),
        search_scope: scope,
        local_match_threshold: threshold,
        top_k: topK,
      });
      setResult(resolved);
      if (resolved.error) {
        setError(resolved.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const exportProvenance = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result.report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `entity-recon-${result.report.query_hash || "report"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="entity-recon" className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <h2 className="text-lg">Entity Recon</h2>
      {error ? (
        <p role="alert" className="rounded border border-it-border bg-it-surface px-2 py-1 text-sm">
          {error}
        </p>
      ) : null}

      {available === false ? (
        <p data-testid="entity-recon-unavailable" className="text-it-muted-text">
          The recon engine is not attached yet — the dataset index arrives with its worker lifecycle.
        </p>
      ) : null}

      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void resolve();
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="entity-recon-image" className="text-it-muted-text">
            Cutout image
          </label>
          <input
            id="entity-recon-image"
            type="text"
            value={imagePath}
            onChange={(event) => setImagePath(event.target.value)}
            placeholder="/absolute/path/to/cutout.png"
            className="w-72 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <button
            type="submit"
            disabled={busy || available === false}
            className="rounded border border-it-border px-3 py-1 text-it-text disabled:opacity-50"
          >
            {busy ? "Resolving…" : "Resolve"}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="entity-recon-scope" className="text-it-muted-text">
            Scope
          </label>
          <select
            id="entity-recon-scope"
            value={scope}
            onChange={(event) => setScope(event.target.value as Scope)}
            className="rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          >
            <option value="local">local (fully offline)</option>
            <option value="web">web (reverse-image discovery)</option>
            <option value="both">both (local first, web fallback)</option>
          </select>
          <label htmlFor="entity-recon-threshold" className="text-it-muted-text">
            Threshold
          </label>
          <input
            id="entity-recon-threshold"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            className="w-16 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <label htmlFor="entity-recon-topk" className="text-it-muted-text">
            Top K
          </label>
          <input
            id="entity-recon-topk"
            type="number"
            min={1}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
            className="w-16 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
        </div>
        {scope !== defaultScope && scope !== "local" ? (
          <p className="text-sm text-it-muted-text" data-testid="entity-recon-web-warning">
            Web scope enables live reverse-image discovery on the configured engines.
          </p>
        ) : null}
      </form>

      {result ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="rounded border border-it-border bg-it-surface p-3 text-sm" data-testid="entity-recon-summary">
            {result.found ? (
              <p>
                <strong>{result.name}</strong> · {(result.confidence * 100).toFixed(1)}% · {result.method}
              </p>
            ) : (
              <p className="text-it-muted-text">No identity resolved ({result.method || "no match"}).</p>
            )}
          </div>

          {result.local_matches.length > 0 ? (
            <section data-testid="entity-recon-local-matches" className="text-sm">
              <h3>Local matches</h3>
              <ul>
                {result.local_matches.map((match, index) => (
                  <li key={`${match.path}-${index}`}>
                    {match.label} · {(match.score * 100).toFixed(1)}% · {match.path}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {result.web_domains.length > 0 ? (
            <section data-testid="entity-recon-web-domains" className="text-sm">
              <h3>Web domains</h3>
              <ul>
                {result.web_domains.map((domain, index) => (
                  <li key={`${domain.domain}-${index}`}>
                    {domain.domain} · {domain.count} hit{domain.count === 1 ? "" : "s"}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section data-testid="entity-recon-provenance" className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border text-sm">
            <h3>Provenance</h3>
            <ul>
              {result.report.entries.map((entry, index) => (
                <li key={index} className="border-b border-it-border px-2 py-1">
                  {entry.kind}
                  {entry.domain ? ` (${entry.domain})` : ""}: {entry.label || entry.source}
                </li>
              ))}
              {result.report.entries.length === 0 ? <li className="px-2 py-1 text-it-muted-text">No provenance entries.</li> : null}
            </ul>
          </section>

          <button
            type="button"
            onClick={exportProvenance}
            className="w-fit rounded border border-it-border px-3 py-1 text-it-text"
          >
            Export provenance JSON
          </button>
        </div>
      ) : (
        <p className="text-it-muted-text" data-testid="entity-recon-idle">
          Pick a cutout and resolve; the provenance report follows the result.
        </p>
      )}
    </div>
  );
}
