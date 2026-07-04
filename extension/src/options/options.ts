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

// --- Site rules editor (§7.10) ---

function addRuleRow(pattern = "", folder = ""): void {
  const list = $<HTMLDivElement>("rules-list");
  const row = document.createElement("div");
  row.className = "rule-row";

  const patternInput = document.createElement("input");
  patternInput.type = "text";
  patternInput.placeholder = "*.example.com";
  patternInput.value = pattern;
  patternInput.className = "rule-pattern";

  const folderInput = document.createElement("input");
  folderInput.type = "text";
  folderInput.placeholder = "folder";
  folderInput.value = folder;
  folderInput.className = "rule-folder";

  const removeBtn = document.createElement("button");
  removeBtn.className = "secondary";
  removeBtn.textContent = "✕";
  removeBtn.title = "Remove rule";
  removeBtn.addEventListener("click", () => row.remove());

  row.append(patternInput, folderInput, removeBtn);
  list.appendChild(row);
}

function collectRules(): Array<{ pattern: string; folder: string }> {
  const rules: Array<{ pattern: string; folder: string }> = [];
  for (const row of document.querySelectorAll<HTMLDivElement>(".rule-row")) {
    const pattern =
      row.querySelector<HTMLInputElement>(".rule-pattern")?.value.trim() ?? "";
    const folder =
      row.querySelector<HTMLInputElement>(".rule-folder")?.value.trim() ?? "";
    if (pattern && folder) rules.push({ pattern, folder });
  }
  return rules;
}

async function restoreOptions(): Promise<void> {
  const settings = await loadSettings();
  $<HTMLInputElement>("folder").value = settings.targetFolder;
  $<HTMLInputElement>("template").value = settings.filenameTemplate;
  $<HTMLInputElement>("turbo").checked = settings.turboMode;
  $<HTMLInputElement>("sidecar").checked = settings.saveSidecar;
  $<HTMLInputElement>("strip-params").checked = settings.dupTabsStripParams;
  $<HTMLInputElement>("bridge-url").value = settings.bridgeUrl;
  $<HTMLInputElement>("bridge-token").value = settings.bridgeToken;
  for (const rule of settings.siteRules) {
    addRuleRow(rule.pattern, rule.folder);
  }
}

async function saveOptions(): Promise<void> {
  const folderName = $<HTMLInputElement>("folder").value;
  // Basic validation to remove forbidden characters (keeping / for subfolders)
  const cleanName = folderName.replace(/[<>:"\\|?*]/g, "");

  await saveSettings({
    targetFolder: cleanName,
    filenameTemplate:
      $<HTMLInputElement>("template").value.trim() || "{name}.{ext}",
    turboMode: $<HTMLInputElement>("turbo").checked,
    saveSidecar: $<HTMLInputElement>("sidecar").checked,
    dupTabsStripParams: $<HTMLInputElement>("strip-params").checked,
    siteRules: collectRules(),
    bridgeUrl:
      $<HTMLInputElement>("bridge-url").value.trim().replace(/\/+$/, "") ||
      "http://127.0.0.1:8000/api/extension",
    bridgeToken: $<HTMLInputElement>("bridge-token").value.trim(),
  });
  $<HTMLInputElement>("folder").value = cleanName;
  showStatus("Settings Saved!");
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
  $<HTMLButtonElement>("add-rule").addEventListener("click", () => {
    addRuleRow();
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
