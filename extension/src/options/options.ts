/**
 * Popup / options page: settings persistence + duplicate-tab scanning (§7.13).
 */
import { api, setActionBadge, storageGet, storageSet } from "../shared/api";
import { loadSettings, saveSettings } from "../shared/settings";
import type { ExtensionSettings } from "../shared/settings";
import { scanAndHighlight, clearHighlights } from "../shared/dupTabs";
import { ping, BridgeError } from "../shared/bridge";
import {
  getCachedPhashSnapshot,
  refreshPhashSnapshot,
} from "../shared/clientPhash";
import type { LastDupCheck, LastSimilar, TurboHistoryEntry } from "../background";
import type { DupTabSet, CollectPageImagesResponse, GalleryData } from "../shared/messages";

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

// --- Folder profiles (§7.10) ---

function addProfileRow(name = ""): void {
  const list = $<HTMLDivElement>("profiles-list");
  const row = document.createElement("div");
  row.className = "profile-row";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.placeholder = "e.g. wallpapers";
  nameInput.value = name;
  nameInput.className = "profile-name";

  const activateBtn = document.createElement("button");
  activateBtn.className = "profile-active";
  activateBtn.textContent = "Activate";
  activateBtn.title = "Switch the default target directory to this profile";
  activateBtn.addEventListener("click", () => {
    void activateProfile(nameInput.value.trim());
  });

  const removeBtn = document.createElement("button");
  removeBtn.className = "secondary";
  removeBtn.textContent = "✕";
  removeBtn.title = "Remove profile";
  removeBtn.addEventListener("click", () => row.remove());

  row.append(nameInput, activateBtn, removeBtn);
  list.appendChild(row);
}

function collectProfiles(): string[] {
  const profiles: string[] = [];
  for (const row of document.querySelectorAll<HTMLDivElement>(".profile-row")) {
    const name = row.querySelector<HTMLInputElement>(".profile-name")?.value.trim() ?? "";
    if (name) profiles.push(name);
  }
  return profiles;
}

/** Quick-switch: make *name* the active default folder immediately. */
async function activateProfile(name: string): Promise<void> {
  if (!name) return;
  const cleanName = name.replace(/[<>:"\\|?*]/g, "");
  await saveSettings({ targetFolder: cleanName, folderProfiles: collectProfiles() });
  $<HTMLInputElement>("folder").value = cleanName;
  showStatus(`Switched to '${cleanName}'`);
}

// --- Turbo Mode site list (§7.12) ---

function addTurboSiteRow(pattern = ""): void {
  const list = $<HTMLDivElement>("turbo-sites-list");
  const row = document.createElement("div");
  row.className = "site-row";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "*.example.com";
  input.value = pattern;
  input.className = "turbo-site-pattern";

  const removeBtn = document.createElement("button");
  removeBtn.className = "secondary";
  removeBtn.textContent = "✕";
  removeBtn.title = "Remove site";
  removeBtn.addEventListener("click", () => row.remove());

  row.append(input, removeBtn);
  list.appendChild(row);
}

function collectTurboSites(): string[] {
  const patterns: string[] = [];
  for (const row of document.querySelectorAll<HTMLDivElement>(".site-row")) {
    const pattern = row.querySelector<HTMLInputElement>(".turbo-site-pattern")?.value.trim() ?? "";
    if (pattern) patterns.push(pattern);
  }
  return patterns;
}

// --- Turbo capture history (§7.12) ---

async function renderTurboHistory(): Promise<void> {
  const { turboHistory, turboCaptureCount } = await storageGet<{
    turboHistory: TurboHistoryEntry[];
    turboCaptureCount: number;
  }>(["turboHistory", "turboCaptureCount"]);

  $<HTMLSpanElement>("turbo-count").textContent = String(turboCaptureCount ?? 0);

  const container = $<HTMLDivElement>("turbo-history");
  container.replaceChildren();
  const history = turboHistory ?? [];
  if (history.length === 0) {
    container.textContent = "No turbo captures yet.";
    return;
  }

  for (const entry of history) {
    const row = document.createElement("div");
    row.className = entry.status === "error" ? "turbo-entry error" : "turbo-entry";

    const urlLine = document.createElement("div");
    urlLine.className = "turbo-entry-url";
    urlLine.textContent = entry.filename;
    row.appendChild(urlLine);

    const meta = document.createElement("div");
    meta.className = "turbo-entry-meta";
    const when = new Date(entry.when).toLocaleString();
    meta.textContent =
      entry.status === "error" ? `${when} — failed: ${entry.error ?? "unknown error"}` : when;
    row.appendChild(meta);

    container.appendChild(row);
  }
}

async function clearTurboHistory(): Promise<void> {
  await storageSet({ turboHistory: [], turboCaptureCount: 0 });
  await setActionBadge("");
  await renderTurboHistory();
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
  $<HTMLSelectElement>("bridge-transport").value = settings.bridgeTransport;
  $<HTMLInputElement>("native-host-name").value = settings.nativeHostName;
  for (const rule of settings.siteRules) {
    addRuleRow(rule.pattern, rule.folder);
  }
  for (const profile of settings.folderProfiles) {
    addProfileRow(profile);
  }
  $<HTMLSelectElement>("turbo-modifier").value = settings.turboModifierKey;
  $<HTMLSelectElement>("turbo-site-mode").value = settings.turboSiteMode;
  for (const pattern of settings.turboSitePatterns) {
    addTurboSiteRow(pattern);
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
    folderProfiles: collectProfiles(),
    turboModifierKey:
      ($<HTMLSelectElement>("turbo-modifier").value as ExtensionSettings["turboModifierKey"]) ||
      "none",
    turboSiteMode:
      ($<HTMLSelectElement>("turbo-site-mode").value as ExtensionSettings["turboSiteMode"]) ||
      "all",
    turboSitePatterns: collectTurboSites(),
    bridgeUrl:
      $<HTMLInputElement>("bridge-url").value.trim().replace(/\/+$/, "") ||
      "http://127.0.0.1:8000/api/extension",
    bridgeToken: $<HTMLInputElement>("bridge-token").value.trim(),
    bridgeTransport:
      ($<HTMLSelectElement>("bridge-transport").value as "http" | "native") ||
      "http",
    nativeHostName:
      $<HTMLInputElement>("native-host-name").value.trim() ||
      "com.imagetoolkit.bridge",
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

// --- Bridge connection test (§7.5) ---

async function testConnection(): Promise<void> {
  const dot = $<HTMLSpanElement>("conn-dot");
  const statusEl = $<HTMLSpanElement>("conn-status");
  dot.className = "conn-dot";
  statusEl.textContent = "testing…";
  // Use the *unsaved* field values so the user can iterate before saving.
  await saveSettings({
    bridgeUrl:
      $<HTMLInputElement>("bridge-url").value.trim().replace(/\/+$/, "") ||
      "http://127.0.0.1:8000/api/extension",
    bridgeToken: $<HTMLInputElement>("bridge-token").value.trim(),
    bridgeTransport:
      ($<HTMLSelectElement>("bridge-transport").value as "http" | "native") ||
      "http",
    nativeHostName:
      $<HTMLInputElement>("native-host-name").value.trim() ||
      "com.imagetoolkit.bridge",
  });
  try {
    const info = await ping();
    dot.className = "conn-dot ok";
    statusEl.textContent = info.dup_root_configured
      ? `connected (bridge v${info.version})`
      : `connected — set a duplicate-search directory in the app`;
  } catch (err) {
    dot.className = "conn-dot fail";
    statusEl.textContent =
      err instanceof BridgeError && err.status === 403
        ? "invalid token"
        : "unreachable — is the Image Toolkit API running?";
  }
}

// --- Shared thumbnail-result row rendering (§7.6 / §7.8) ---

/** Common shape of a ranked/matched library result with an optional thumb. */
interface ThumbResultItem {
  path: string;
  thumb_b64: string | null;
  width: number | null;
  height: number | null;
}

/**
 * Render one row per result: thumbnail + click-to-copy label. Shared by the
 * duplicate-check (§7.6) and find-similar (§7.8) result panels — `labelFor`
 * supplies the per-feature score/distance prefix.
 */
function renderThumbResults<T extends ThumbResultItem>(
  container: HTMLElement,
  items: T[],
  labelFor: (item: T) => string,
): void {
  for (const m of items) {
    const row = document.createElement("div");
    row.className = "dup-tab-row";
    if (m.thumb_b64) {
      const img = document.createElement("img");
      img.src = `data:image/jpeg;base64,${m.thumb_b64}`;
      img.style.width = "48px";
      img.style.height = "48px";
      img.style.objectFit = "cover";
      img.style.borderRadius = "3px";
      row.appendChild(img);
    }
    const label = document.createElement("span");
    label.className = "dup-tab-title";
    label.textContent = labelFor(m);
    label.title = "Copy path";
    label.addEventListener("click", () => {
      void navigator.clipboard.writeText(m.path);
    });
    row.appendChild(label);
    container.appendChild(row);
  }
}

function dimsSuffix(m: ThumbResultItem): string {
  return m.width ? ` (${m.width}×${m.height})` : "";
}

// --- Last duplicate-check result (§7.6) ---

async function renderLastDupCheck(): Promise<void> {
  const container = $<HTMLDivElement>("dupcheck-results");
  const { lastDupCheck } = await storageGet<{ lastDupCheck: LastDupCheck }>(
    "lastDupCheck",
  );
  if (!lastDupCheck) return;
  container.replaceChildren();

  const header = document.createElement("div");
  header.style.marginBottom = "6px";
  const when = new Date(lastDupCheck.when).toLocaleString();
  if (lastDupCheck.error) {
    header.textContent = `${when} — failed: ${lastDupCheck.error}`;
    container.appendChild(header);
    return;
  }
  const result = lastDupCheck.result;
  if (!result) return;
  header.textContent =
    result.matches.length === 0
      ? `${when} — no duplicates (${result.scanned} files checked)`
      : `${when} — ${result.matches.length} match(es) in ${result.scanned} files:`;
  container.appendChild(header);

  renderThumbResults(
    container,
    result.matches,
    (m) => `[d=${m.hamming}] ${m.path}${dimsSuffix(m)}`,
  );
}

// --- Last find-similar result (§7.8) ---

async function renderLastSimilar(): Promise<void> {
  const container = $<HTMLDivElement>("similar-results");
  const { lastSimilar } = await storageGet<{ lastSimilar: LastSimilar }>(
    "lastSimilar",
  );
  if (!lastSimilar) return;
  container.replaceChildren();

  const header = document.createElement("div");
  header.style.marginBottom = "6px";
  const when = new Date(lastSimilar.when).toLocaleString();
  if (lastSimilar.error) {
    header.textContent = `${when} — failed: ${lastSimilar.error}`;
    container.appendChild(header);
    return;
  }
  const result = lastSimilar.result;
  if (!result) return;
  header.textContent =
    result.results.length === 0
      ? `${when} — no results (${result.scanned} files checked)`
      : `${when} — top ${result.results.length} of ${result.scanned} files ` +
        `(ranked by ${result.method}):`;
  container.appendChild(header);

  renderThumbResults(
    container,
    result.results,
    (m) => `[score=${m.score.toFixed(2)}] ${m.path}${dimsSuffix(m)}`,
  );
}

// --- Local pHash pre-check (§7.16C) ---

function formatSnapshotStatus(
  cache: Awaited<ReturnType<typeof getCachedPhashSnapshot>>,
): string {
  if (!cache) return "not cached yet";
  const when = new Date(cache.cachedAt).toLocaleString();
  return `${cache.hashes.length} hashes cached ${when}`;
}

async function renderSnapshotStatus(): Promise<void> {
  const statusEl = $<HTMLSpanElement>("snapshot-status");
  statusEl.textContent = formatSnapshotStatus(await getCachedPhashSnapshot());
}

async function refreshSnapshot(): Promise<void> {
  const statusEl = $<HTMLSpanElement>("snapshot-status");
  statusEl.textContent = "refreshing…";
  try {
    const cache = await refreshPhashSnapshot();
    statusEl.textContent = formatSnapshotStatus(cache);
  } catch (err) {
    statusEl.textContent =
      err instanceof BridgeError ? `failed: ${err.message}` : `failed: ${String(err)}`;
  }
}

// --- Page capture (§7.9) ---

type CaptureAction = "download_all_media" | "start_selection_overlay";

async function sendToActiveTab(action: CaptureAction): Promise<void> {
  const statusEl = $<HTMLDivElement>("capture-status");
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    statusEl.textContent = "No active tab.";
    return;
  }
  try {
    const resp = (await api.tabs.sendMessage(tab.id, { action })) as
      | { ok: boolean; images?: number; videos?: number }
      | undefined;
    if (action === "download_all_media" && resp?.ok) {
      const total = (resp.images ?? 0) + (resp.videos ?? 0);
      statusEl.textContent =
        total === 0
          ? "No downloadable media found on this page."
          : `Queued ${resp.images ?? 0} image(s) + ${resp.videos ?? 0} video(s).`;
    } else if (action === "start_selection_overlay" && resp?.ok) {
      statusEl.textContent = "Selection mode active — click images in the page.";
      window.close(); // hand focus to the page overlay
    }
  } catch {
    statusEl.textContent =
      "Cannot capture on this page (browser-internal pages are blocked).";
  }
}

/**
 * Grid-preview page (§7.9C): collect the page's detected images via the
 * content script, stash them under `galleryData` for the new tab to read
 * (see `GalleryData`), then open `gallery.html`. Reuses the same content-
 * script round trip as `sendToActiveTab` but doesn't download anything.
 */
async function openGridPreview(): Promise<void> {
  const statusEl = $<HTMLDivElement>("capture-status");
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    statusEl.textContent = "No active tab.";
    return;
  }
  try {
    const resp = (await api.tabs.sendMessage(tab.id, {
      action: "collect_page_images",
    })) as CollectPageImagesResponse | undefined;
    if (!resp?.ok) {
      statusEl.textContent = "Could not scan this page.";
      return;
    }
    const galleryData: GalleryData = {
      pageUrl: resp.pageUrl,
      images: resp.images,
      capturedAt: new Date().toISOString(),
    };
    await storageSet({ galleryData });
    await api.tabs.create({ url: api.runtime.getURL("gallery.html") });
  } catch {
    statusEl.textContent =
      "Cannot capture on this page (browser-internal pages are blocked).";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  void restoreOptions();
  void renderLastDupCheck();
  void renderLastSimilar();
  void renderSnapshotStatus();
  void renderTurboHistory();
  $<HTMLButtonElement>("refresh-snapshot").addEventListener("click", () => {
    void refreshSnapshot();
  });
  $<HTMLButtonElement>("download-all").addEventListener("click", () => {
    void sendToActiveTab("download_all_media");
  });
  $<HTMLButtonElement>("select-images").addEventListener("click", () => {
    void sendToActiveTab("start_selection_overlay");
  });
  $<HTMLButtonElement>("grid-preview").addEventListener("click", () => {
    void openGridPreview();
  });
  $<HTMLButtonElement>("test-conn").addEventListener("click", () => {
    void testConnection();
  });
  $<HTMLButtonElement>("save").addEventListener("click", () => {
    void saveOptions();
  });
  $<HTMLButtonElement>("add-rule").addEventListener("click", () => {
    addRuleRow();
  });
  $<HTMLButtonElement>("add-profile").addEventListener("click", () => {
    addProfileRow();
  });
  $<HTMLButtonElement>("add-turbo-site").addEventListener("click", () => {
    addTurboSiteRow();
  });
  $<HTMLButtonElement>("clear-turbo-history").addEventListener("click", () => {
    void clearTurboHistory();
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
