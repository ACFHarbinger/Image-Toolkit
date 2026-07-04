/**
 * Popup / options page: settings persistence + duplicate-tab scanning (§7.13).
 */
import { api } from "../shared/api";
import { loadSettings, saveSettings } from "../shared/settings";
import { scanAndHighlight, clearHighlights } from "../shared/dupTabs";
import type { DupTabSet } from "../shared/messages";

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

// --- Duplicate tab scanning (§7.13) ---

function renderDupSets(sets: DupTabSet[], grouped: boolean): void {
  const container = $<HTMLDivElement>("dup-results");
  container.replaceChildren();

  if (sets.length === 0) {
    container.textContent = "No duplicate tabs in this window. ✓";
    return;
  }

  const summary = document.createElement("div");
  const extra = grouped ? " Highlighted with colored tab groups." : "";
  summary.textContent = `${sets.length} duplicate set(s) found.${extra}`;
  summary.style.marginBottom = "6px";
  container.appendChild(summary);

  for (const set of sets) {
    const box = document.createElement("div");
    box.className = "dup-set";

    const urlDiv = document.createElement("div");
    urlDiv.className = "dup-set-url";
    urlDiv.textContent = `${set.url} (×${set.tabs.length})`;
    box.appendChild(urlDiv);

    set.tabs.forEach((tab, idx) => {
      const row = document.createElement("div");
      row.className = "dup-tab-row";

      const title = document.createElement("span");
      title.className = "dup-tab-title";
      title.textContent = tab.title;
      title.title = "Switch to this tab";
      title.addEventListener("click", () => {
        void api.tabs.update(tab.id, { active: true });
        void api.windows.update(tab.windowId, { focused: true });
      });
      row.appendChild(title);

      if (idx > 0) {
        const closeBtn = document.createElement("button");
        closeBtn.className = "secondary";
        closeBtn.textContent = "Close";
        closeBtn.addEventListener("click", () => {
          void api.tabs.remove(tab.id).then(() => row.remove());
        });
        row.appendChild(closeBtn);
      }
      box.appendChild(row);
    });

    const actions = document.createElement("div");
    actions.className = "dup-actions";
    const closeOthers = document.createElement("button");
    closeOthers.textContent = "Keep first, close rest";
    closeOthers.addEventListener("click", () => {
      const ids = set.tabs.slice(1).map((t) => t.id);
      void api.tabs.remove(ids).then(() => box.remove());
    });
    actions.appendChild(closeOthers);
    box.appendChild(actions);

    container.appendChild(box);
  }
}

async function scanDuplicateTabs(): Promise<void> {
  const settings = await loadSettings();
  const result = await scanAndHighlight(settings.dupTabsStripParams);
  renderDupSets(result.sets, result.grouped);
}

document.addEventListener("DOMContentLoaded", () => {
  void restoreOptions();
  $<HTMLButtonElement>("save").addEventListener("click", () => {
    void saveOptions();
  });
  $<HTMLButtonElement>("scan-dups").addEventListener("click", () => {
    void scanDuplicateTabs();
  });
  $<HTMLButtonElement>("clear-dups").addEventListener("click", () => {
    void clearHighlights().then(() => {
      $<HTMLDivElement>("dup-results").replaceChildren();
    });
  });
});
