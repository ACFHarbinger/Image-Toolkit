import {
  CatalogAlias,
  CatalogEntry,
  CatalogWindow,
  shellCatalog,
} from "./catalog";

const FRONTEND_SURFACE = "frontend";

/** Stitch panels share the editor rail. The catalog still records them as Image Stitching. */
export const EDITOR_CATEGORY = "Image Editor";
const STITCH_CATEGORY = "Image Stitching";

export function railCategory(category: string): string {
  return category === STITCH_CATEGORY ? EDITOR_CATEGORY : category;
}

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
    if (entry.kind === "route" || entry.category === STITCH_CATEGORY) {
      continue;
    }
    const category = railCategory(entry.category);
    if (!seen.includes(category)) {
      seen.push(category);
    }
  }
  return seen;
}

/**
 * Drawer rows for one category. Routes stay off the rail and belong on
 * the workspace ribbon, except the stitch panels, which are the editor
 * tabs. The stitch workspace row is only a container, so it stays hidden.
 */
export function drawerEntries(
  entries: readonly CatalogEntry[],
  category: string,
): CatalogEntry[] {
  if (category === EDITOR_CATEGORY) {
    const pages = entries.filter(
      (entry) => entry.category === EDITOR_CATEGORY && entry.kind === "page",
    );
    const stitchTabs = entries
      .filter((entry) => entry.category === STITCH_CATEGORY && entry.kind === "route")
      .sort((left, right) => left.order_index - right.order_index);
    return [...pages, ...stitchTabs];
  }
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

/** Pages and workspaces for one classic category. Stitch's workspace sits under Image Editor. */
export function classicPages(
  entries: readonly CatalogEntry[],
  category: string,
): CatalogEntry[] {
  return entries.filter(
    (entry) => railCategory(entry.category) === category && entry.kind !== "route",
  );
}

/** Child routes of a workspace page. Ordinary pages have none. */
export function classicSubtabs(
  entries: readonly CatalogEntry[],
  page: CatalogEntry | undefined,
): CatalogEntry[] {
  if (!page || page.kind !== "workspace") {
    return [];
  }
  return ribbonRoutes(entries, page.id);
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
