// Cloud Jobs settings view (Gate D5 / #851): caps, thresholds, retention,
// packing, fallback, notifications and regions on the #880 settings
// service, read and written whole through the `cloud_jobs/settings` key.
// The risk rule editor rides the jobs capability when that surface opens.

import React, { useState } from "react";
import type { HostClient } from "../../hostclient";
import {
  CLOUD_JOBS_SECTIONS,
  CLOUD_JOBS_SETTINGS_KEY,
  type CloudJobsSettingsDocument,
  type Field,
} from "./cloudSettings";

export interface CloudJobsSettingsProps {
  hostClient: HostClient;
}

type Phase = "loading" | "ready" | "saving" | "error";

function isDocument(value: unknown): value is CloudJobsSettingsDocument {
  return typeof value === "object" && value !== null && "packing_mode" in value;
}

export function CloudJobsSettings({ hostClient }: CloudJobsSettingsProps) {
  const [document, setDocument] = useState<CloudJobsSettingsDocument | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");

  const load = React.useCallback(async () => {
    setPhase("loading");
    try {
      const result = await hostClient.getSetting({ key: CLOUD_JOBS_SETTINGS_KEY });
      if (!isDocument(result.value)) {
        throw new Error("the settings document is malformed");
      }
      setDocument(result.value);
      setError("");
      setPhase("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("error");
    }
  }, [hostClient]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!document) {
      return;
    }
    setPhase("saving");
    try {
      const result = await hostClient.setSetting({
        key: CLOUD_JOBS_SETTINGS_KEY,
        value: document as unknown as Record<string, unknown>,
      });
      if (!isDocument(result.value)) {
        throw new Error("the settings document is malformed");
      }
      setDocument(result.value);
      setError("");
      setPhase("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("ready");
    }
  };

  if (phase === "loading" || !document) {
    return <p data-testid="cloud-jobs-settings-status">Loading Cloud Jobs settings…</p>;
  }

  const setField = (key: keyof CloudJobsSettingsDocument, value: unknown) => {
    setDocument({ ...document, [key]: value } as CloudJobsSettingsDocument);
  };

  return (
    <main className="flex min-h-screen flex-col gap-4 p-6" data-testid="cloud-jobs-settings">
      <header className="flex items-center justify-between">
        <h1 className="text-xl">Cloud Jobs settings</h1>
        <button
          type="button"
          onClick={() => void save()}
          disabled={phase !== "ready"}
          className="rounded border border-it-border px-3 py-1 text-it-text disabled:opacity-50"
        >
          {phase === "saving" ? "Saving…" : "Save"}
        </button>
      </header>
      {error ? (
        <p role="alert" className="rounded border border-it-border bg-it-surface px-3 py-2">
          {error}
        </p>
      ) : null}
      {CLOUD_JOBS_SECTIONS.map((section) => (
        <section
          key={section.id}
          data-testid={`cloud-jobs-section-${section.id}`}
          className="rounded border border-it-border bg-it-surface p-4"
        >
          <h2 className="mb-3 text-base">{section.title}</h2>
          <div className="flex flex-col gap-3">
            {section.fields.map((field) => (
              <FieldRow
                key={field.key}
                field={field}
                document={document}
                onChange={(value) => setField(field.key as keyof CloudJobsSettingsDocument, value)}
              />
            ))}
            {section.id === "placement" ? (
              <RegionsEditor
                regions={document.default_regions}
                onChange={(regions) => setField("default_regions", regions)}
              />
            ) : null}
          </div>
        </section>
      ))}
    </main>
  );
}

function FieldRow({
  field,
  document,
  onChange,
}: {
  field: Field;
  document: CloudJobsSettingsDocument;
  onChange: (value: unknown) => void;
}) {
  const label = (
    <label className="w-56 shrink-0 text-it-muted-text" htmlFor={`setting-${field.key}`}>
      {field.label}
    </label>
  );
  const record = document as unknown as Record<string, unknown>;
  return (
    <div className="flex items-center gap-3">
      {label}
      {field.kind === "toggle" ? (
        <input
          id={`setting-${field.key}`}
          type="checkbox"
          checked={Boolean(record[field.key])}
          onChange={(event) => onChange(event.target.checked)}
          data-testid={`setting-${field.key}`}
        />
      ) : field.kind === "select" ? (
        <select
          id={`setting-${field.key}`}
          value={String(record[field.key])}
          onChange={(event) => onChange(event.target.value)}
          data-testid={`setting-${field.key}`}
          className="rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
        >
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : field.kind === "text" ? (
        <input
          id={`setting-${field.key}`}
          type="text"
          value={String(record[field.key] ?? "")}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
          data-testid={`setting-${field.key}`}
          className="grow rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
        />
      ) : field.kind === "number" ? (
        <>
          <input
            id={`setting-${field.key}`}
            type="number"
            value={String(record[field.key] ?? "")}
            min={field.min}
            step={field.step}
            onChange={(event) => onChange(event.target.value === "" ? "" : Number(event.target.value))}
            data-testid={`setting-${field.key}`}
            className="w-32 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          {field.unit ? <span className="text-it-muted-text">{field.unit}</span> : null}
        </>
      ) : (
        <input
          id={`setting-${field.key}`}
          type="text"
          value={(record[field.key] as string[]).join(", ")}
          placeholder={field.hint}
          onChange={(event) =>
            onChange(
              event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            )
          }
          data-testid={`setting-${field.key}`}
          className="grow rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
        />
      )}
    </div>
  );
}

function RegionsEditor({
  regions,
  onChange,
}: {
  regions: Record<string, string>;
  onChange: (regions: Record<string, string>) => void;
}) {
  const entries = Object.entries(regions).sort(([a], [b]) => a.localeCompare(b));
  return (
    <div className="flex flex-col gap-2" data-testid="default-regions-editor">
      <span className="w-56 shrink-0 text-it-muted-text">Default regions</span>
      {entries.map(([provider, region]) => (
        <div key={provider} className="flex items-center gap-2 pl-56">
          <input
            type="text"
            value={provider}
            aria-label={`region provider ${provider}`}
            onChange={(event) => {
              const next = { ...regions };
              delete next[provider];
              next[event.target.value] = region;
              onChange(next);
            }}
            className="w-40 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <input
            type="text"
            value={region}
            aria-label={`region for ${provider}`}
            onChange={(event) => onChange({ ...regions, [provider]: event.target.value })}
            className="w-40 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <button
            type="button"
            onClick={() => {
              const next = { ...regions };
              delete next[provider];
              onChange(next);
            }}
            className="rounded border border-it-border px-2 py-1 text-it-text"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="pl-56">
        <button
          type="button"
          onClick={() => onChange({ ...regions, "": "" })}
          className="rounded border border-it-border px-2 py-1 text-it-text"
        >
          Add region
        </button>
      </div>
    </div>
  );
}
