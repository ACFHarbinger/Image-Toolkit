import document from "./catalog.json";

export interface CatalogEntry {
  id: string;
  title: string;
  category: string;
  kind: "page" | "workspace" | "route";
  order_index: number;
  window_id: string;
  workspace_id: string | null;
  route_key: string | null;
  icon_name: string;
  capability_flags: string[];
  search_terms: string[];
  surfaces: string[];
  legacy_frontend_id: string | null;
  companion_window_id: string | null;
}

export interface CatalogWindow {
  id: string;
  role: "main" | "tray" | "slideshow" | "popout";
  panel_of: string | null;
}

export const shellCatalog = document;

export function frontendPages(): CatalogEntry[] {
  return (document.entries as CatalogEntry[])
    .filter(
      (entry) =>
        entry.kind === "page" &&
        entry.surfaces.includes("frontend") &&
        entry.legacy_frontend_id !== null,
    )
    .sort((left, right) => left.order_index - right.order_index);
}
