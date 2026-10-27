import React, { useEffect, useState } from "react";
import type {
  PrefsGallery,
  PrefsGetResult,
  PrefsLogging,
  PrefsProfiles,
  PrefsSetParams,
  PrefsSetResult,
} from "../../../../contracts/generated/ts/prefs";

export interface SettingsClient {
  prefsGet(account: string): Promise<PrefsGetResult>;
  prefsSet(params: PrefsSetParams): Promise<PrefsSetResult>;
}

const TABS = [
  ["account", "Account"],
  ["profiles", "Profiles"],
  ["gallery", "Gallery"],
  ["logging", "Logging"],
  ["shortcuts", "Shortcuts"],
] as const;

type TabId = (typeof TABS)[number][0];

const LEVELS: readonly PrefsLogging["level"][] = ["DEBUG", "INFO", "WARNING", "ERROR"];

function documentOf(result: PrefsGetResult | PrefsSetResult): PrefsGetResult {
  return {
    account: result.account,
    profiles: result.profiles,
    gallery: result.gallery,
    logging: result.logging,
    shortcuts: result.shortcuts,
  };
}

/** Settings window (#1112). Loads the Qt-free store, edits it, and shows the saved values. */
export function SettingsWindow({
  hostClient,
  account,
  onClose,
}: {
  readonly hostClient: SettingsClient;
  readonly account: string;
  readonly onClose: () => void;
}): React.ReactElement {
  const [form, setForm] = useState<PrefsGetResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [active, setActive] = useState<TabId>("account");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [shortcutAction, setShortcutAction] = useState("");
  const [shortcutChord, setShortcutChord] = useState("");

  useEffect(() => {
    let cancelled = false;
    setForm(null);
    setError("");
    setNotice("");
    setCurrentPassword("");
    setNewPassword("");
    hostClient.prefsGet(account).then(
      (next) => {
        if (cancelled) {
          return;
        }
        const first = next.shortcuts[0]?.id ?? "";
        setForm(documentOf(next));
        setShortcutAction(first);
        setShortcutChord(next.shortcuts.find((row) => row.id === first)?.custom ?? "");
      },
      (exc: unknown) => {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "settings load failed");
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [hostClient, account]);

  const patchProfiles = (patch: Partial<PrefsProfiles>) => {
    setForm((current) => (current ? { ...current, profiles: { ...current.profiles, ...patch } } : current));
  };
  const patchGallery = (patch: Partial<PrefsGallery>) => {
    setForm((current) => (current ? { ...current, gallery: { ...current.gallery, ...patch } } : current));
  };
  const patchLogging = (patch: Partial<PrefsLogging>) => {
    setForm((current) => (current ? { ...current, logging: { ...current.logging, ...patch } } : current));
  };

  const onWhole = (key: "thumbnail_size" | "page_size", raw: string) => {
    const next = Number(raw);
    if (!Number.isInteger(next)) {
      return;
    }
    patchGallery({ [key]: next });
  };

  const save = () => {
    if (!form) {
      return;
    }
    setError("");
    const params: PrefsSetParams = {
      account,
      current_password: currentPassword,
      new_password: newPassword,
      profiles: form.profiles,
      gallery: form.gallery,
      logging: form.logging,
      ...(shortcutAction && shortcutChord !== (form.shortcuts.find((row) => row.id === shortcutAction)?.custom ?? "") ? { shortcut: { action: shortcutAction, chord: shortcutChord } } : {}),
    };
    hostClient.prefsSet(params).then(
      (next) => {
        const saved = documentOf(next);
        const chord = saved.shortcuts.find((row) => row.id === shortcutAction)?.custom ?? "";
        setForm(saved);
        setShortcutChord(chord);
        setCurrentPassword("");
        setNewPassword("");
        setNotice(next.reason);
      },
      (exc: unknown) => {
        setError(exc instanceof Error ? exc.message : "settings save failed");
      },
    );
  };

  const selectAction = (action: string) => {
    setShortcutAction(action);
    setShortcutChord(form?.shortcuts.find((row) => row.id === action)?.custom ?? "");
  };

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
        {notice ? (
          <p role="status" className="px-6 py-4">
            {notice}
          </p>
        ) : null}
        <div role="tablist" aria-label="Settings sections" className="flex flex-wrap border-b border-gray-200 dark:border-gray-700">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`settings-tab-${id}`}
              aria-selected={active === id}
              aria-controls={`settings-panel-${id}`}
              onClick={() => setActive(id)}
              className="px-4 py-3 font-medium"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {form && active === "account" ? (
            <section role="tabpanel" id="settings-panel-account" aria-labelledby="settings-tab-account" className="space-y-4">
              <label className="block text-sm font-medium" htmlFor="setting-account">
                Account name
                <input id="setting-account" className="mt-1 w-full rounded border px-3 py-2" readOnly value={form.account} />
              </label>
              <label className="block text-sm font-medium" htmlFor="setting-current-password">
                Current password
                <input
                  id="setting-current-password"
                  className="mt-1 w-full rounded border px-3 py-2"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                />
              </label>
              <label className="block text-sm font-medium" htmlFor="setting-new-password">
                New master password
                <input
                  id="setting-new-password"
                  className="mt-1 w-full rounded border px-3 py-2"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </label>
            </section>
          ) : null}
          {form && active === "profiles" ? (
            <section role="tabpanel" id="settings-panel-profiles" aria-labelledby="settings-tab-profiles" className="space-y-4">
              <label className="block text-sm font-medium" htmlFor="setting-startup-category">
                Startup category
                <input
                  id="setting-startup-category"
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={form.profiles.startup_category}
                  onChange={(event) => patchProfiles({ startup_category: event.target.value })}
                />
              </label>
              <label className="block text-sm font-medium" htmlFor="setting-startup-tab">
                Startup tab
                <input
                  id="setting-startup-tab"
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={form.profiles.startup_tab}
                  onChange={(event) => patchProfiles({ startup_tab: event.target.value })}
                />
              </label>
            </section>
          ) : null}
          {form && active === "gallery" ? (
            <section role="tabpanel" id="settings-panel-gallery" aria-labelledby="settings-tab-gallery" className="space-y-4">
              <label className="block text-sm font-medium" htmlFor="setting-thumbnail-size">
                Thumbnail size
                <input
                  id="setting-thumbnail-size"
                  className="mt-1 w-full rounded border px-3 py-2"
                  type="number"
                  value={form.gallery.thumbnail_size}
                  onChange={(event) => onWhole("thumbnail_size", event.target.value)}
                />
              </label>
              <label className="block text-sm font-medium" htmlFor="setting-page-size">
                Page size
                <input
                  id="setting-page-size"
                  className="mt-1 w-full rounded border px-3 py-2"
                  type="number"
                  value={form.gallery.page_size}
                  onChange={(event) => onWhole("page_size", event.target.value)}
                />
              </label>
              <label className="flex items-center gap-2 text-sm" htmlFor="setting-confirm-deletions">
                <input
                  id="setting-confirm-deletions"
                  type="checkbox"
                  checked={form.gallery.confirm_deletions}
                  onChange={(event) => patchGallery({ confirm_deletions: event.target.checked })}
                />
                Confirm deletions
              </label>
              <label className="flex items-center gap-2 text-sm" htmlFor="setting-recursive-scan">
                <input
                  id="setting-recursive-scan"
                  type="checkbox"
                  checked={form.gallery.recursive_scan}
                  onChange={(event) => patchGallery({ recursive_scan: event.target.checked })}
                />
                Recursive scan
              </label>
            </section>
          ) : null}
          {form && active === "logging" ? (
            <section role="tabpanel" id="settings-panel-logging" aria-labelledby="settings-tab-logging" className="space-y-4">
              <label className="block text-sm font-medium" htmlFor="setting-log-level">
                Log level
                <select
                  id="setting-log-level"
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={form.logging.level}
                  onChange={(event) => patchLogging({ level: event.target.value as PrefsLogging["level"] })}
                >
                  {LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm" htmlFor="setting-file-logging">
                <input
                  id="setting-file-logging"
                  type="checkbox"
                  checked={form.logging.file_logging}
                  onChange={(event) => patchLogging({ file_logging: event.target.checked })}
                />
                File logging
              </label>
            </section>
          ) : null}
          {form && active === "shortcuts" ? (
            <section role="tabpanel" id="settings-panel-shortcuts" aria-labelledby="settings-tab-shortcuts" className="space-y-4">
              <ul aria-label="Shortcut actions" className="max-h-48 space-y-1 overflow-y-auto text-sm">
                {form.shortcuts.map((row) => (
                  <li key={row.id}>
                    {row.description} ({row.default}
                    {row.custom ? `, ${row.custom}` : ""})
                  </li>
                ))}
              </ul>
              <label className="block text-sm font-medium" htmlFor="setting-shortcut-action">
                Shortcut action
                <select
                  id="setting-shortcut-action"
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={shortcutAction}
                  onChange={(event) => selectAction(event.target.value)}
                >
                  {form.shortcuts.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium" htmlFor="setting-shortcut-chord">
                Shortcut chord
                <input
                  id="setting-shortcut-chord"
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={shortcutChord}
                  onChange={(event) => setShortcutChord(event.target.value)}
                />
              </label>
            </section>
          ) : null}
        </div>
        <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-700">
          <button type="button" onClick={save} disabled={!form} className="rounded-lg bg-violet-700 px-4 py-2 text-white">
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
