/**
 * Typed storage.local settings schema with defaults (§7.2).
 */
import { storageGet, storageSet } from "./api";

export interface ExtensionSettings {
  /** Subfolder of Downloads/ that captures are saved into. */
  targetFolder: string;
  /** Turbo mode: left-click any image to download it. */
  turboMode: boolean;
  /** Duplicate-tab scan: also strip common tracking params when normalizing URLs. */
  dupTabsStripParams: boolean;
}

export const DEFAULT_SETTINGS: ExtensionSettings = {
  targetFolder: "data",
  turboMode: false,
  dupTabsStripParams: true,
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
