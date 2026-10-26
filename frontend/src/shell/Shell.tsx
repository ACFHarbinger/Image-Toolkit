import { ReactNode, useEffect, useMemo, useState } from "react";
import { LogOut, Moon, Settings, Sun } from "lucide-react";
import { HostClient, RustTransport } from "../hostclient";
import { useAppStore } from "../store/appStore";
import { SettingsWindow } from "../views/settings/SettingsWindow";
import { shellCatalog } from "./catalog";
import { ClassicShell } from "./classic/ClassicShell";
import { Inspector } from "./Inspector";
import { StatusBar, DbStatus } from "./StatusBar";
import { CatalogView } from "./views";
import { CloudComputeSurface } from "./CloudComputeSurface";
import { CloudJobsControl } from "./CloudJobsControl";
import { CloudJobsWindow } from "./CloudJobsWindow";
import { popOut } from "./windows";
import { useCloudBadge } from "./useCloudBadge";
import {
  ACTIVE_ALIAS_GATES,
  defaultPageId,
  entryById,
  frontendEntries,
  resolveAlias,
  windowFor,
} from "./navigation";

interface ShellProps {
  showModal: (
    message: string | ReactNode,
    type?: "info" | "error" | "success",
    duration?: number,
  ) => void;
}

export function Shell({ showModal }: ShellProps) {
  const { logout, openSettings, closeSettings, showSettings, setDatabaseConnected, setTheme, preferences, vault } = useAppStore();
  const entries = useMemo(() => frontendEntries(), []);
  const [activeId, setActiveId] = useState(() => defaultPageId(entries));
  const active = entryById(entries, activeId);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [dbStatus, setDbStatus] = useState<DbStatus>("disconnected");
  const [hostClient, setHostClient] = useState<HostClient | null>(null);
  const [computeOpen, setComputeOpen] = useState(false);
  const [jobsFallback, setJobsFallback] = useState(false);
  const cloudBadge = useCloudBadge(hostClient);

  useEffect(() => {
    // Each effect setup owns its client, including StrictMode's setup/cleanup replay.
    const client = new HostClient(new RustTransport(), {
      clientName: "tauri-shell",
      // Protocol compatibility, not the app semver. COMPATIBILITY_MAX is 1.0.0.
      clientVersion: "1.0.0",
    });
    setHostClient(client);
    void client.connect().catch(() => {});
    return () => { void client.close(); };
  }, []);

  useEffect(() => {
    if (!hostClient) {
      setDbStatus("disconnected");
      setDatabaseConnected(false);
      return;
    }
    let cancelled = false;
    setDbStatus("checking");
    hostClient
      .listLibraryGroups()
      .then((result) => {
        if (cancelled) {
          return;
        }
        const connected = result.available === true;
        setDbStatus(connected ? "connected" : "disconnected");
        setDatabaseConnected(connected);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setDbStatus("disconnected");
        setDatabaseConnected(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hostClient, setDatabaseConnected]);

  const selectModule = (id: string) => {
    const resolved = resolveAlias(id, shellCatalog.aliases, ACTIVE_ALIAS_GATES);
    const next = entryById(entries, resolved);
    if (!next) {
      return;
    }
    setActiveId(next.id);
    setJobsFallback(false);
    setComputeOpen(false);
  };

  const windowRole = windowFor(shellCatalog.windows, active?.window_id ?? "main")?.role ?? "main";

  useEffect(() => {
    if (!hostClient || !vault?.accountName) {
      return;
    }
    let cancelled = false;
    hostClient
      .authStatus({ account: vault.accountName })
      .then((status) => {
        if (!cancelled && status.unlocked === false) {
          logout();
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [hostClient, vault?.accountName, logout]);

  const onLogout = () => {
    const account = vault?.accountName ?? "";
    const finish = () => logout();
    if (!hostClient || !account) {
      finish();
      return;
    }
    void hostClient.authLock({ account }).then(finish, finish);
  };

  const onAddImagesToDb = (files: File[]) => {
    showModal(`Attempting to add ${files.length} images to the database...`, "info");
  };

  const openJobs = () => {
    setComputeOpen(false);
    void popOut("cloud.jobs").catch(() => {
      setJobsFallback(true);
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 font-sans dark:bg-gray-900 sm:p-8">
      {showSettings && hostClient ? (
        <SettingsWindow hostClient={hostClient} account={vault?.accountName ?? ""} onClose={closeSettings} />
      ) : null}
      <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-6xl flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800">
        <header className="flex items-center justify-between bg-violet-700 p-4 text-white">
          <h1 className="text-2xl font-extrabold tracking-tight">Image Database and Toolkit</h1>
          <div className="flex items-center gap-2">
            <CloudJobsControl
              badge={cloudBadge}
              onOpenJobs={openJobs}
              onOpenCompute={() => {
                setJobsFallback(false);
                setComputeOpen(true);
              }}
            />
            <button
              type="button"
              aria-label="Toggle theme"
              title="Toggle theme"
              onClick={() => setTheme(preferences.theme === "dark" ? "light" : "dark")}
              className="rounded-lg p-2 hover:bg-violet-600"
            >
              {preferences.theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <button type="button" onClick={openSettings} aria-label="Settings" className="rounded-lg p-2 hover:bg-violet-600" title="Settings">
              <Settings size={20} />
            </button>
            <button type="button" onClick={onLogout} aria-label="Logout" className="rounded-lg p-2 hover:bg-violet-600" title="Logout">
              <LogOut size={20} />
            </button>
          </div>
        </header>
        <div className="flex min-h-0 flex-1">
          <ClassicShell entries={entries} activeId={activeId} onSelect={selectModule}>
            <main
              className={
                activeId === "developer.benchmarks"
                  ? "min-h-0 flex-1 overflow-hidden"
                  : "min-h-0 flex-1 overflow-y-auto bg-it-window-bg"
              }
            >
              {jobsFallback ? (
                <CloudJobsWindow badge={cloudBadge} hostClient={hostClient} />
              ) : computeOpen ? (
                <CloudComputeSurface hostClient={hostClient} onClose={() => setComputeOpen(false)} />
              ) : (
                active &&
                hostClient && (
                  <CatalogView
                    entry={active}
                    showModal={showModal}
                    onAddImagesToDb={onAddImagesToDb}
                    hostClient={hostClient}
                  />
                )
              )}
            </main>
          </ClassicShell>
          <Inspector entry={active} open={inspectorOpen} onToggle={() => setInspectorOpen((open) => !open)} />
        </div>
        <StatusBar dbStatus={dbStatus} activeId={activeId} windowRole={windowRole} />
      </div>
    </div>
  );
}
