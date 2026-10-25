// Cloud Compute setup window (T-04 / #920): providers, credentials,
// request builder, and dashboards. Opened from the header gear or a
// shift-click on the Cloud Jobs control. Provider descriptors ride the
// `cloud_setup.providers` capability; non-secret setup config persists
// through the settings capability (`cloud_setup/profiles`, ACCOUNT
// scope). Real credentials live in the vault and never transit the
// bridge — attaching them rides the vault unlock (#918 / #879), so the
// credentials tab reports that state instead of a password field.
// Request Builder is D4's (#992); the dashboards are D3's (#990).

import React, { useEffect, useState } from "react";
import type { ProviderDescriptor } from "../../../contracts/generated/ts";
import type { HostClient } from "../hostclient";
import { RequestBuilder } from "../views/cloudjobs/RequestBuilder";
import { ResourcesView, SpendView, type CloudResources, type CloudSpend } from "./CloudJobsViews";

const EMPTY_RESOURCES: CloudResources = { available: false, resources: [] };
const EMPTY_SPEND: CloudSpend = { available: false, month_actual_usd: 0, reserved_usd: 0, by_provider: [] };
const PROFILES_KEY = "cloud_setup/profiles";

type Tab = "providers" | "credentials" | "builder" | "dashboards";

export interface CloudComputeSurfaceProps {
  hostClient: HostClient | null;
  onClose: () => void;
}

export function CloudComputeSurface({ hostClient, onClose }: CloudComputeSurfaceProps): React.ReactElement {
  const [tab, setTab] = useState<Tab>("providers");
  const [providers, setProviders] = useState<ProviderDescriptor[]>([]);
  const [error, setError] = useState("");
  const [profiles, setProfiles] = useState<Record<string, { region?: string; endpoint?: string }>>({});

  useEffect(() => {
    let cancelled = false;
    if (!hostClient) {
      return;
    }
    const load = async () => {
      try {
        const [catalog, settings] = await Promise.all([
          hostClient.cloudSetupProviders(),
          hostClient.getSetting({ key: PROFILES_KEY }),
        ]);
        if (cancelled) return;
        setProviders(catalog.providers);
        const stored = settings.value as Record<string, { region?: string; endpoint?: string }> | null;
        setProfiles(stored ?? {});
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

  const saveProfile = async (providerId: string, next: { region?: string; endpoint?: string }) => {
    if (!hostClient) return;
    const merged = { ...profiles, [providerId]: next };
    try {
      await hostClient.setSetting({ key: PROFILES_KEY, value: merged });
      setProfiles(merged);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <section data-testid="cloud-compute-surface" className="flex min-h-0 flex-1 flex-col gap-3 p-6">
      <header className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Cloud Compute</h2>
        <button type="button" onClick={onClose} className="rounded border border-it-border px-3 py-1">
          Back
        </button>
      </header>

      <nav className="flex items-center gap-2" data-testid="cloud-compute-tabs">
        {(
          [
            ["providers", "Providers"],
            ["credentials", "Credentials"],
            ["builder", "Request Builder"],
            ["dashboards", "Dashboards"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            data-testid={`cloud-compute-tab-${id}`}
            aria-pressed={tab === id}
            onClick={() => setTab(id)}
            className={`rounded px-3 py-1 text-sm ${
              tab === id ? "bg-it-accent text-it-window-bg" : "border border-it-border text-it-text"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {error ? (
        <p role="alert" className="rounded border border-it-border bg-it-surface px-2 py-1 text-sm">
          {error}
        </p>
      ) : null}

      {tab === "providers" ? (
        <div className="grid min-h-0 flex-1 gap-3 overflow-y-auto md:grid-cols-2" data-testid="cloud-compute-providers">
          {providers.map((provider) => (
            <article
              key={provider.provider_id}
              data-testid={`cloud-provider-card-${provider.provider_id}`}
              className="flex flex-col gap-1 rounded border border-it-border bg-it-surface p-3 text-sm"
            >
              <header className="flex items-center justify-between gap-2">
                <h3 className="font-semibold">{provider.name}</h3>
                <span data-testid={`cloud-provider-badge-${provider.provider_id}`} className="text-it-muted-text">
                  {provider.badge_text}
                </span>
              </header>
              <p className="text-it-muted-text">{provider.description}</p>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                <dt className="text-it-muted-text">Service</dt>
                <dd>{provider.target_service}</dd>
                <dt className="text-it-muted-text">CPU</dt>
                <dd>{provider.cpu_shapes}</dd>
                <dt className="text-it-muted-text">Memory</dt>
                <dd>{provider.memory_tiers}</dd>
                <dt className="text-it-muted-text">GPU</dt>
                <dd>{provider.gpu_options}</dd>
                <dt className="text-it-muted-text">Cost</dt>
                <dd>{provider.cost_estimate}</dd>
                <dt className="text-it-muted-text">Cold start</dt>
                <dd>{provider.cold_start}</dd>
                <dt className="text-it-muted-text">Regions</dt>
                <dd>{provider.regions.join(", ")}</dd>
              </dl>
            </article>
          ))}
          {providers.length === 0 ? <p className="text-it-muted-text">Loading providers…</p> : null}
        </div>
      ) : null}

      {tab === "credentials" ? (
        <CredentialsPanel providers={providers} profiles={profiles} onSave={saveProfile} />
      ) : null}

      {tab === "builder" ? (
        hostClient ? (
          <div className="min-h-0 flex-1 overflow-y-auto" data-testid="cloud-compute-builder">
            <RequestBuilder client={hostClient} />
          </div>
        ) : (
          <p className="text-it-muted-text">Connect the bridge to use the Request Builder.</p>
        )
      ) : null}

      {tab === "dashboards" ? <DashboardsPanel hostClient={hostClient} /> : null}
    </section>
  );
}

function CredentialsPanel({
  providers,
  profiles,
  onSave,
}: {
  providers: ProviderDescriptor[];
  profiles: Record<string, { region?: string; endpoint?: string }>;
  onSave: (providerId: string, next: { region?: string; endpoint?: string }) => Promise<void>;
}): React.ReactElement {
  const [selected, setSelected] = useState("");
  const active = providers.find((provider) => provider.provider_id === selected) ?? providers[0];
  const profile = (active && profiles[active.provider_id]) || {};

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3" data-testid="cloud-compute-credentials">
      <div className="flex flex-wrap gap-2">
        {providers.map((provider) => (
          <button
            key={provider.provider_id}
            type="button"
            aria-pressed={active?.provider_id === provider.provider_id}
            onClick={() => setSelected(provider.provider_id)}
            className={`rounded px-3 py-1 text-sm ${
              active?.provider_id === provider.provider_id
                ? "bg-it-accent text-it-window-bg"
                : "border border-it-border text-it-text"
            }`}
          >
            {provider.name}
          </button>
        ))}
      </div>

      {active ? (
        <ProviderProfileForm
          providerId={active.provider_id}
          region={profile.region ?? ""}
          endpoint={profile.endpoint ?? ""}
          onSave={onSave}
        />
      ) : (
        <p className="text-it-muted-text">Loading providers…</p>
      )}

      <p className="text-sm text-it-muted-text" data-testid="cloud-credentials-vault-notice">
        Credentials live in the vault and never transit the bridge. Attaching them rides the vault unlock.
      </p>
    </div>
  );
}

function ProviderProfileForm({
  providerId,
  region,
  endpoint,
  onSave,
}: {
  providerId: string;
  region: string;
  endpoint: string;
  onSave: (providerId: string, next: { region?: string; endpoint?: string }) => Promise<void>;
}): React.ReactElement {
  const [regionValue, setRegionValue] = useState(region);
  const [endpointValue, setEndpointValue] = useState(endpoint);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRegionValue(region);
    setEndpointValue(endpoint);
  }, [providerId, region, endpoint]);

  return (
    <form
      className="flex flex-col gap-2"
      data-testid={`cloud-profile-form-${providerId}`}
      onSubmit={(event) => {
        event.preventDefault();
        setSaving(true);
        void onSave(providerId, {
          region: regionValue.trim() || undefined,
          endpoint: endpointValue.trim() || undefined,
        }).finally(() => setSaving(false));
      }}
    >
      <label htmlFor={`cloud-profile-region-${providerId}`} className="text-it-muted-text">
        Preferred region
      </label>
      <input
        id={`cloud-profile-region-${providerId}`}
        type="text"
        value={regionValue}
        onChange={(event) => setRegionValue(event.target.value)}
        className="w-64 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
      />
      <label htmlFor={`cloud-profile-endpoint-${providerId}`} className="text-it-muted-text">
        Endpoint (non-secret)
      </label>
      <input
        id={`cloud-profile-endpoint-${providerId}`}
        type="text"
        value={endpointValue}
        onChange={(event) => setEndpointValue(event.target.value)}
        className="w-64 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
      />
      <button type="submit" disabled={saving} className="w-fit rounded border border-it-border px-3 py-1 disabled:opacity-50">
        {saving ? "Saving…" : "Save setup config"}
      </button>
    </form>
  );
}

function DashboardsPanel({ hostClient }: { hostClient: HostClient | null }): React.ReactElement {
  const [resources, setResources] = useState<CloudResources>(EMPTY_RESOURCES);
  const [spend, setSpend] = useState<CloudSpend>(EMPTY_SPEND);

  useEffect(() => {
    let cancelled = false;
    if (!hostClient) {
      return;
    }
    const load = async () => {
      try {
        const [resourcesResult, spendResult] = await Promise.all([
          hostClient.cloudJobsResources(),
          hostClient.cloudJobsSpend(),
        ]);
        if (cancelled) return;
        setResources(resourcesResult as unknown as CloudResources);
        setSpend(spendResult as unknown as CloudSpend);
      } catch {
        if (!cancelled) {
          setResources(EMPTY_RESOURCES);
          setSpend(EMPTY_SPEND);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [hostClient]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto" data-testid="cloud-compute-dashboards">
      <ResourcesView view={resources} notice="" onTerminate={() => {}} />
      <SpendView view={spend} />
    </div>
  );
}
