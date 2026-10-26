// Reverse image search (B-05 / #910): the HostClient-driven view for
// `web.reverse-search`, riding the `reverse_search` capability over the
// existing middleware strategies (Google Lens, TinEye, SauceNAO, IQDB,
// Bing, Yandex, Local AI Search). Replaces the legacy UI-only stub. A
// search runs the live engine at the user's request; this view never
// fabricates results.

import React, { useEffect, useState } from "react";
import type {
  EngineRecord,
  ReverseSearchResultItem,
} from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";

export interface ReverseSearchViewProps {
  hostClient: HostClient;
}

type Phase = "loading" | "ready" | "searching";

export function ReverseSearchView({ hostClient }: ReverseSearchViewProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [engines, setEngines] = useState<EngineRecord[]>([]);
  const [engine, setEngine] = useState<string>("");
  const [imagePath, setImagePath] = useState("");
  const [limit, setLimit] = useState(20);
  const [roi, setRoi] = useState("");
  const [results, setResults] = useState<ReverseSearchResultItem[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const catalog = await hostClient.reverseSearchEngines();
        if (cancelled) return;
        setEngines(catalog.engines);
        setEngine((current) => current || catalog.engines[0]?.id || "");
        setPhase("ready");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setPhase("ready");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [hostClient]);

  const search = async () => {
    if (!imagePath.trim()) {
      setError("Pick an image to search with first.");
      return;
    }
    setError("");
    setPhase("searching");
    try {
      const roiValues = roi
        .split(",")
        .map((component) => Number(component.trim()))
        .filter((value) => Number.isFinite(value));
      const result = await hostClient.reverseSearch({
        engine: engine as EngineRecord["id"],
        image_path: imagePath.trim(),
        limit,
        roi: roiValues.length === 4 ? roiValues : undefined,
      });
      setResults(result.results);
      setSearched(true);
      if (!result.ok && result.error) {
        setError(result.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPhase("ready");
    }
  };

  return (
    <div data-testid="reverse-search" className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <h2 className="text-lg">Reverse Search</h2>
      {error ? (
        <p role="alert" className="rounded border border-it-border bg-it-surface px-2 py-1 text-sm">
          {error}
        </p>
      ) : null}

      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="reverse-search-engine" className="text-it-muted-text">
            Engine
          </label>
          <select
            id="reverse-search-engine"
            value={engine}
            onChange={(event) => setEngine(event.target.value)}
            className="rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          >
            {engines.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.label}
              </option>
            ))}
          </select>
          <label htmlFor="reverse-search-image" className="text-it-muted-text">
            Image
          </label>
          <input
            id="reverse-search-image"
            type="text"
            value={imagePath}
            onChange={(event) => setImagePath(event.target.value)}
            placeholder="/absolute/path/to/query.png"
            className="w-72 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <label htmlFor="reverse-search-limit" className="text-it-muted-text">
            Limit
          </label>
          <input
            id="reverse-search-limit"
            type="number"
            min={1}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value) || 20)}
            className="w-16 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <button
            type="submit"
            disabled={phase !== "ready"}
            className="rounded border border-it-border px-3 py-1 text-it-text disabled:opacity-50"
          >
            {phase === "searching" ? "Searching…" : "Search"}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="reverse-search-roi" className="text-it-muted-text">
            ROI (x, y, w, h)
          </label>
          <input
            id="reverse-search-roi"
            type="text"
            value={roi}
            onChange={(event) => setRoi(event.target.value)}
            placeholder="optional crop region"
            className="w-40 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
        </div>
      </form>

      {searched ? (
        <div
          className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border"
          data-testid="reverse-search-results"
        >
          {results.map((item, index) => (
            <div
              key={`${item.url}-${index}`}
              className="flex items-center justify-between gap-2 border-b border-it-border px-2 py-1 text-sm"
            >
              <span className="truncate" title={item.url}>
                {item.title || item.url}
              </span>
              <span className="shrink-0 text-it-muted-text">
                {item.resolution} · {(item.score * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {results.length === 0 ? (
            <p className="p-2 text-it-muted-text">No matches for this query.</p>
          ) : null}
        </div>
      ) : (
        <p className="text-it-muted-text" data-testid="reverse-search-idle">
          Pick an engine and an image, then search.
        </p>
      )}
    </div>
  );
}
