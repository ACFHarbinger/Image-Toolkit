/**
 * Typed storage.local settings schema with defaults (§7.2).
 */
import { storageGet, storageSet } from "./api";

/** One per-site folder rule (§7.10): first matching pattern wins. */
export interface SiteRule {
  /** Hostname pattern; `*` wildcards allowed (e.g. `*.pixiv.net`). */
  pattern: string;
  /** Downloads/ subfolder used when the rule matches. */
  folder: string;
}

export interface ExtensionSettings {
  /** Subfolder of Downloads/ that captures are saved into. */
  targetFolder: string;
  /** Turbo mode: left-click any image to download it. */
  turboMode: boolean;
  /** Duplicate-tab scan: also strip common tracking params when normalizing URLs. */
  dupTabsStripParams: boolean;
  /** Per-site folder rules, evaluated top-to-bottom against the page hostname. */
  siteRules: SiteRule[];
  /**
   * Filename template (§7.10). Tokens: {name} {ext} {site} {date} {time}.
   * May contain `/` to create subfolders below the resolved folder.
   */
  filenameTemplate: string;
  /** Also write a `<filename>.json` provenance sidecar next to each download. */
  saveSidecar: boolean;
  /** Base URL of the Image Toolkit bridge (§7.5A). */
  bridgeUrl: string;
  /** Bearer token pasted from the desktop app's settings. */
  bridgeToken: string;
}

export const DEFAULT_SETTINGS: ExtensionSettings = {
  targetFolder: "data",
  turboMode: false,
  dupTabsStripParams: true,
  siteRules: [],
  filenameTemplate: "{name}.{ext}",
  saveSidecar: false,
  bridgeUrl: "http://127.0.0.1:8000/api/extension",
  bridgeToken: "",
};

export async function loadSettings(): Promise<ExtensionSettings> {
  const stored = await storageGet<ExtensionSettings>(
    Object.keys(DEFAULT_SETTINGS),
  );
  return { ...DEFAULT_SETTINGS, ...stored };
}

export async function saveSettings(
  patch: Partial<ExtensionSettings>,
): Promise<void> {
  await storageSet(patch);
}
