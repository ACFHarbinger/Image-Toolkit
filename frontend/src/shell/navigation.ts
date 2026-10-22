import {
  CatalogAlias,
  CatalogEntry,
  CatalogWindow,
  shellCatalog,
} from "./catalog";

const FRONTEND_SURFACE = "frontend";

/**
 * Alias gates that are on for this shell. `experimental-dl` stays off:
 * the classic `ml.*` pages remain the views until that workspace is the
 * default. Turning the gate on resolves those ids to `dl.*` routes.
 */
export const ACTIVE_ALIAS_GATES: ReadonlySet<string> = new Set();

export function frontendEntries(
  entries: readonly CatalogEntry[] = shellCatalog.entries,
): CatalogEntry[] {
  return entries.filter((entry) => entry.surfaces.includes(FRONTEND_SURFACE));
}

export function entryById(
  entries: readonly CatalogEntry[],
  id: string,
): CatalogEntry | undefined {
  return entries.find((entry) => entry.id === id);
}

export function defaultPageId(entries: readonly CatalogEntry[]): string {
  return entries.find((entry) => entry.kind === "page")?.id ?? "";
}

/** Category order follows the catalog document, skipping child routes. */
export function categoriesInOrder(entries: readonly CatalogEntry[]): string[] {
  const seen: string[] = [];
  for (const entry of entries) {
    if (entry.kind === "route") {
      continue;
    }
    if (!seen.includes(entry.category)) {
      seen.push(entry.category);
    }
  }
  return seen;
}

/**
 * Drawer rows for one category. Routes stay off the rail; they belong
 * on the workspace ribbon. Selecting a category only repaints this list.
 */
export function drawerEntries(
  entries: readonly CatalogEntry[],
  category: string,
): CatalogEntry[] {
  return entries.filter(
    (entry) => entry.category === category && entry.kind !== "route",
  );
}

export function workspaceIdFor(entry: CatalogEntry | undefined): string | null {
  if (!entry) {
    return null;
  }
  if (entry.kind === "workspace") {
    return entry.id;
  }
  if (entry.kind === "route") {
    return entry.workspace_id;
  }
  return null;
}

export function ribbonRoutes(
  entries: readonly CatalogEntry[],
  workspaceId: string | null,
): CatalogEntry[] {
  if (!workspaceId) {
    return [];
  }
  return entries
    .filter((entry) => entry.kind === "route" && entry.workspace_id === workspaceId)
    .sort((left, right) => left.order_index - right.order_index);
}

export function resolveAlias(
  id: string,
  aliases: readonly CatalogAlias[],
  appliesWhen: ReadonlySet<string>,
): string {
  const match = aliases.find(
    (alias) => alias.alias_id === id && appliesWhen.has(alias.applies_when),
  );
  return match ? match.target_id : id;
}

export function windowFor(
  windows: readonly CatalogWindow[],
  windowId: string,
): CatalogWindow | undefined {
  return windows.find((window) => window.id === windowId);
}
