// Cloud Jobs settings view (Gate D5 / #851): caps, thresholds, retention,
// packing, fallback, notifications and regions on the #880 settings
// service, read and written whole through the `cloud_jobs/settings` key.
// The risk rule editor rides the jobs capability when that surface opens.

import React, { useState } from "react";
import { RegionsEditor } from "./RegionsEditor";
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
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const regions = record.default_regions;
  if (typeof regions !== "object" || regions === null || Array.isArray(regions) ||
      !Object.values(regions).every((region) => typeof region === "string")) return false;
  return CLOUD_JOBS_SECTIONS.every((section) => section.fields.every((field) => {
    const entry = record[field.key];
    switch (field.kind) {
      case "toggle": return typeof entry === "boolean";
      case "number": return typeof entry === "number" && Number.isFinite(entry);
      case "select":
      case "text": return typeof entry === "string";
      case "list": return Array.isArray(entry) && entry.every((item) => typeof item === "string");
    }
  }));
}

export function CloudJobsSettings({ hostClient }: CloudJobsSettingsProps) {
  const [document, setDocument] = useState<CloudJobsSettingsDocument | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");
  const [regionsValid, setRegionsValid] = useState(true);
  const [regionVersion, setRegionVersion] = useState(0);

  const load = React.useCallback(async () => {
    setPhase("loading");
    try {
      const result = await hostClient.getSetting({ key: CLOUD_JOBS_SETTINGS_KEY });
      if (!isDocument(result.value)) {
        throw new Error("the settings document is malformed");
      }
      setDocument(result.value);
      setRegionsValid(true);
      setRegionVersion((version) => version + 1);
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
    if (!document || !regionsValid) {
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
      setRegionsValid(true);
      setRegionVersion((version) => version + 1);
      setError("");
      setPhase("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("ready");
    }
  };

  if (phase === "error") {
    return (
      <div className="flex flex-col gap-4">
        <p role="alert">Could not load Cloud Jobs settings: {error}</p>
        <button type="button" onClick={() => void load()}>Retry</button>
      </div>
    );
  }

  if (phase === "loading" || !document) {
    return <p data-testid="cloud-jobs-settings-status">Loading Cloud Jobs settings…</p>;
  }

  const setField = (key: keyof CloudJobsSettingsDocument, value: unknown) => {
    setDocument({ ...document, [key]: value } as CloudJobsSettingsDocument);
  };

  return (
    <div className="flex flex-col gap-4" data-testid="cloud-jobs-settings">
      <header className="flex items-center justify-between">
        <h1 className="text-xl">Cloud Jobs settings</h1>
        <button
          type="button"
          onClick={() => void save()}
          disabled={phase !== "ready" || !regionsValid}
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
                key={regionVersion}
                onValidityChange={setRegionsValid}
                regions={document.default_regions}
                onChange={(regions) => setField("default_regions", regions)}
              />
            ) : null}
          </div>
        </section>
      ))}
    </div>
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
