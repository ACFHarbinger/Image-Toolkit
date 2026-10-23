import { ReactNode, useEffect, useMemo, useState } from "react";
import { LogOut, Settings } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { HostClient, RustTransport } from "../hostclient";
import { useAppStore } from "../store/appStore";
import { shellCatalog } from "./catalog";
import { Inspector } from "./Inspector";
import { Rail } from "./Rail";
import { Ribbon } from "./Ribbon";
import { StatusBar, DbStatus } from "./StatusBar";
import { CatalogView } from "./views";
import {
  ACTIVE_ALIAS_GATES,
  categoriesInOrder,
  defaultPageId,
  drawerEntries,
  entryById,
  frontendEntries,
  resolveAlias,
  ribbonRoutes,
  windowFor,
  workspaceIdFor,
} from "./navigation";

interface ShellProps {
  showModal: (
    message: string | ReactNode,
    type?: "info" | "error" | "success",
    duration?: number,
  ) => void;
}

export function Shell({ showModal }: ShellProps) {
  const { logout, openSettings, setDatabaseConnected } = useAppStore();
  const entries = useMemo(() => frontendEntries(), []);
  const categories = useMemo(() => categoriesInOrder(entries), [entries]);
  const [activeId, setActiveId] = useState(() => defaultPageId(entries));
  const active = entryById(entries, activeId);
  const [category, setCategory] = useState(active?.category ?? categories[0] ?? "");
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [dbStatus, setDbStatus] = useState<DbStatus>("checking");
  const [hostClient, setHostClient] = useState<HostClient | null>(null);

  useEffect(() => {
    // Each effect setup owns its client, including StrictMode's setup/cleanup replay.
    const client = new HostClient(new RustTransport(), {
      clientName: "tauri-shell",
      clientVersion: "1.0.0",
    });
    setHostClient(client);
    void client.connect().catch(() => {});
    return () => { void client.close(); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    invoke("test_database_connection")
      .then(() => {
        if (cancelled) {
          return;
        }
        setDbStatus("connected");
        setDatabaseConnected(true);
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
  }, [setDatabaseConnected]);

  const selectModule = (id: string) => {
    const resolved = resolveAlias(id, shellCatalog.aliases, ACTIVE_ALIAS_GATES);
    const next = entryById(entries, resolved);
    if (!next) {
      return;
    }
    setActiveId(next.id);
    setCategory(next.category);
  };

  const workspaceId = workspaceIdFor(active);
  const workspace = workspaceId ? entryById(entries, workspaceId) : undefined;
  const routes = ribbonRoutes(entries, workspaceId);
  const windowRole = windowFor(shellCatalog.windows, active?.window_id ?? "main")?.role ?? "main";

  const onAddImagesToDb = (files: File[]) => {
    showModal(`Attempting to add ${files.length} images to the database...`, "info");
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 font-sans dark:bg-gray-900 sm:p-8">
      <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-6xl flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800">
        <header className="flex items-center justify-between bg-violet-700 p-4 text-white">
          <h1 className="text-2xl font-extrabold tracking-tight">Image Database and Toolkit</h1>
          <div className="flex items-center gap-2">
            <button type="button" onClick={openSettings} className="rounded-lg p-2 hover:bg-violet-600" title="Settings">
              <Settings size={20} />
            </button>
            <button type="button" onClick={logout} className="rounded-lg p-2 hover:bg-violet-600" title="Logout">
              <LogOut size={20} />
            </button>
          </div>
        </header>
        <div className="flex min-h-0 flex-1">
          <Rail
            categories={categories}
            activeCategory={category}
            rows={drawerEntries(entries, category)}
            activeId={activeId}
            drawerOpen={drawerOpen}
            onSelectCategory={setCategory}
            onSelectModule={selectModule}
            onToggleDrawer={() => setDrawerOpen((open) => !open)}
          />
          <div className="flex min-w-0 flex-1 flex-col">
            <Ribbon
              workspaceTitle={workspace?.title ?? ""}
              routes={routes}
              activeId={activeId}
              onSelectModule={selectModule}
            />
            <main
              className={
                activeId === "developer.benchmarks"
                  ? "min-h-0 flex-1 overflow-hidden"
                  : "min-h-0 flex-1 overflow-y-auto"
              }
            >
              {active && (
                <CatalogView
                  entry={active}
                  showModal={showModal}
                  onAddImagesToDb={onAddImagesToDb}
                  hostClient={hostClient ?? undefined}
                />
              )}
            </main>
          </div>
          <Inspector entry={active} open={inspectorOpen} onToggle={() => setInspectorOpen((open) => !open)} />
        </div>
        <StatusBar dbStatus={dbStatus} activeId={activeId} windowRole={windowRole} />
      </div>
    </div>
  );
}
