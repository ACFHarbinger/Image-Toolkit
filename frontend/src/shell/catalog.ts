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

export interface CatalogAlias {
  alias_id: string;
  target_id: string;
  applies_when: string;
}

export interface CatalogDocument {
  version: number;
  entries: CatalogEntry[];
  aliases: CatalogAlias[];
  windows: CatalogWindow[];
}

export const shellCatalog = document as CatalogDocument;
