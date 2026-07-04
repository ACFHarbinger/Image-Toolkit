/**
 * Popup / options page: settings persistence.
 */
import { loadSettings, saveSettings } from "../shared/settings";

const $ = <T extends HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

function showStatus(text: string): void {
  const status = $<HTMLDivElement>("status");
  status.textContent = text;
  setTimeout(() => {
    status.textContent = "";
  }, 1500);
}

async function restoreOptions(): Promise<void> {
  const settings = await loadSettings();
  $<HTMLInputElement>("folder").value = settings.targetFolder;
  $<HTMLInputElement>("turbo").checked = settings.turboMode;
  $<HTMLInputElement>("strip-params").checked = settings.dupTabsStripParams;
}

async function saveOptions(): Promise<void> {
  const folderName = $<HTMLInputElement>("folder").value;
  // Basic validation to remove forbidden characters (keeping / for subfolders)
  const cleanName = folderName.replace(/[<>:"\\|?*]/g, "");

  await saveSettings({
    targetFolder: cleanName,
    turboMode: $<HTMLInputElement>("turbo").checked,
    dupTabsStripParams: $<HTMLInputElement>("strip-params").checked,
  });
  $<HTMLInputElement>("folder").value = cleanName;
  showStatus("Directory Saved!");
}

document.addEventListener("DOMContentLoaded", () => {
  void restoreOptions();
  $<HTMLButtonElement>("save").addEventListener("click", () => {
    void saveOptions();
  });
});
