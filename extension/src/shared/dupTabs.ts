/**
 * Duplicate tab detection & highlighting (§7.13).
 *
 * Scans all tabs in the current window, groups them by normalized URL, and
 * highlights each duplicate set. On Chromium the strongest native signal is a
 * colored tab group per set (chrome.tabs.group + tabGroups.update); Firefox
 * has no tabGroups API, so the popup renders the sets instead and the badge
 * shows the duplicate count.
 */
import { api } from "./api";
import type { DupTabSet, ScanDupTabsResult } from "./messages";

/** Tracking params stripped during normalization when the option is enabled. */
const TRACKING_PARAM_PATTERNS = [
  /^utm_/i,
  /^fbclid$/i,
  /^gclid$/i,
  /^dclid$/i,
  /^msclkid$/i,
  /^mc_(cid|eid)$/i,
  /^igshid$/i,
  /^ref_?(src|url)?$/i,
  /^_ga$/i,
];

/** Group colors cycled across duplicate sets (Chromium tabGroups palette). */
const GROUP_COLORS: chrome.tabGroups.ColorEnum[] = [
  "red",
  "yellow",
  "green",
  "cyan",
  "purple",
  "orange",
  "pink",
  "blue",
];

/**
 * Normalize a URL for duplicate comparison: case-fold protocol/host, drop the
 * fragment, and optionally strip known tracking params (preserving all other
 * query params — two genuinely different gallery pages must not collide).
 */
export function normalizeUrl(rawUrl: string, stripParams: boolean): string {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return rawUrl;
  }
  url.hash = "";
  if (stripParams) {
    const toDelete: string[] = [];
    url.searchParams.forEach((_value, key) => {
      if (TRACKING_PARAM_PATTERNS.some((re) => re.test(key))) {
        toDelete.push(key);
      }
    });
    for (const key of toDelete) url.searchParams.delete(key);
  }
  url.protocol = url.protocol.toLowerCase();
  url.hostname = url.hostname.toLowerCase();
  return url.toString();
}

/** Find duplicate sets among the given tabs. */
export function findDuplicateSets(
  tabs: chrome.tabs.Tab[],
  stripParams: boolean,
): DupTabSet[] {
  const byUrl = new Map<string, chrome.tabs.Tab[]>();
  for (const tab of tabs) {
    const raw = tab.url || tab.pendingUrl;
    if (!raw || tab.id === undefined) continue;
    const key = normalizeUrl(raw, stripParams);
    const list = byUrl.get(key);
    if (list) list.push(tab);
    else byUrl.set(key, [tab]);
  }

  const sets: DupTabSet[] = [];
  for (const [url, group] of byUrl) {
    if (group.length < 2) continue;
    sets.push({
      url,
      tabs: group.map((t) => ({
        id: t.id as number,
        windowId: t.windowId,
        title: t.title ?? url,
        favIconUrl: t.favIconUrl,
      })),
    });
  }
  // Stable order: biggest sets first
  sets.sort((a, b) => b.tabs.length - a.tabs.length);
  return sets;
}

function tabGroupsAvailable(): boolean {
  return (
    typeof chrome !== "undefined" &&
    !!chrome.tabs?.group &&
    !!(chrome as unknown as { tabGroups?: unknown }).tabGroups
  );
}

/** Move each duplicate set into a colored tab group (Chromium only). */
async function highlightWithGroups(sets: DupTabSet[]): Promise<void> {
  for (let i = 0; i < sets.length; i++) {
    const set = sets[i];
    const groupId = await chrome.tabs.group({
      tabIds: set.tabs.map((t) => t.id),
    });
    await chrome.tabGroups.update(groupId, {
      color: GROUP_COLORS[i % GROUP_COLORS.length],
      title: `dup ×${set.tabs.length}`,
    });
  }
}

async function setBadge(count: number): Promise<void> {
  const action = api.action ?? // MV3
    (api as unknown as { browserAction?: typeof chrome.action }).browserAction;
  if (!action) return;
  await action.setBadgeText({ text: count > 0 ? String(count) : "" });
  if (count > 0 && action.setBadgeBackgroundColor) {
    await action.setBadgeBackgroundColor({ color: "#e74c3c" });
  }
}

/**
 * Scan the current window for duplicate tabs and highlight them.
 * Returns the sets so the popup can render them (Firefox path).
 */
export async function scanAndHighlight(
  stripParams: boolean,
): Promise<ScanDupTabsResult> {
  const tabs = await api.tabs.query({ currentWindow: true });
  const sets = findDuplicateSets(tabs, stripParams);
  const totalDuplicates = sets.reduce((n, s) => n + s.tabs.length - 1, 0);

  let grouped = false;
  if (sets.length > 0 && tabGroupsAvailable()) {
    try {
      await highlightWithGroups(sets);
      grouped = true;
    } catch (err) {
      console.warn("[Image-Toolkit] tab grouping failed:", err);
    }
  }
  await setBadge(totalDuplicates);

  return { sets, totalDuplicates, grouped };
}

/** Remove highlight groups (only ones this extension created) and clear the badge. */
export async function clearHighlights(): Promise<void> {
  if (tabGroupsAvailable()) {
    try {
      // Only dissolve groups we created, identified by the "dup ×N" title —
      // never touch the user's own tab groups.
      const groups = await chrome.tabGroups.query({});
      const ourGroupIds = new Set(
        groups.filter((g) => g.title?.startsWith("dup ×")).map((g) => g.id),
      );
      if (ourGroupIds.size > 0) {
        const tabs = await api.tabs.query({});
        const groupedIds = tabs
          .filter((t) => t.id !== undefined && ourGroupIds.has(t.groupId))
          .map((t) => t.id as number);
        if (groupedIds.length > 0) {
          await chrome.tabs.ungroup(groupedIds);
        }
      }
    } catch (err) {
      console.warn("[Image-Toolkit] ungroup failed:", err);
    }
  }
  await setBadge(0);
}
