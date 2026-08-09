const HUB_TAB_KEY = "image-toolkit-docs-hub-tab";

export function persistHubTab(tabId: string): void {
  try {
    localStorage.setItem(HUB_TAB_KEY, tabId);
  } catch {
    /* storage unavailable (private browsing, SSR) — non-fatal */
  }
}

export function readPersistedHubTab(fallback: string): string {
  try {
    return localStorage.getItem(HUB_TAB_KEY) ?? fallback;
  } catch {
    return fallback;
  }
}
