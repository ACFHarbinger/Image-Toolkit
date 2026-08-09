/** Cross-island UI state — read by hub panels and the multi-framework islands
 * they mount (React/Aurelia/Astro) so all four frameworks agree on which hub
 * tab is active without prop-drilling through the Vue tree. */
export interface AppState {
  activeHubTab: string;
  sidebarCollapsed: boolean;
}

export const initialAppState: AppState = {
  activeHubTab: "modules",
  sidebarCollapsed: false,
};
