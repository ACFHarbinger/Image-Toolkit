import React, { useRef, useState } from "react";

interface RegionRow { id: number; provider: string; region: string }

export function RegionsEditor({ regions, onChange, onValidityChange, disabled = false }: {
  regions: Record<string, string>;
  onChange: (regions: Record<string, string>) => void;
  onValidityChange: (valid: boolean) => void;
  disabled?: boolean;
}) {
  const [rows, setRows] = useState<RegionRow[]>(() => Object.entries(regions)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([provider, region], id) => ({ id, provider, region })));
  const nextId = useRef(rows.length);
  const [error, setError] = useState<string | null>(null);

  const update = (next: RegionRow[]) => {
    if (disabled) return;
    const names = next.map((row) => row.provider.trim().toLowerCase());
    const problem = new Set(names).size !== names.length ? "Provider names must be unique."
      : next.some((row) => !row.provider.trim() || !row.region.trim()) ? "Each provider and region must be filled in." : null;
    setRows(next);
    setError(problem);
    onValidityChange(problem === null);
    // Keep invalid drafts local so duplicate names cannot overwrite another row.
    if (!problem) onChange(Object.fromEntries(next.map((row, i) => [names[i], row.region.trim()])));
  };

  return (
    <div className="flex flex-col gap-2" data-testid="default-regions-editor">
      <span className="w-56 shrink-0 text-it-muted-text">Default regions</span>
      {rows.map((row) => (
        <div key={row.id} className="flex items-center gap-2 pl-56">
          <input type="text" value={row.provider} aria-label={`region provider ${row.provider}`}
            disabled={disabled}
            onChange={(event) => update(rows.map((item) => item.id === row.id ? { ...item, provider: event.target.value } : item))}
            className="w-40 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text" />
          <input type="text" value={row.region} aria-label={`region for ${row.provider}`}
            disabled={disabled}
            onChange={(event) => update(rows.map((item) => item.id === row.id ? { ...item, region: event.target.value } : item))}
            className="w-40 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text" />
          <button type="button" disabled={disabled} onClick={() => update(rows.filter((item) => item.id !== row.id))}
            className="rounded border border-it-border px-2 py-1 text-it-text">Remove</button>
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
      <div className="pl-56">
        <button type="button" disabled={disabled} onClick={() => update([...rows, { id: nextId.current++, provider: "", region: "" }])}
          className="rounded border border-it-border px-2 py-1 text-it-text">Add region</button>
      </div>
    </div>
  );
}
