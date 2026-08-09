import { computed } from "vue";
import { useStore } from "vuex";
import type { AppState } from "../state/appState";
import { ActionType } from "../actions/actionTypes";

/** Typed convenience wrapper around `useStore()` for the app-wide Vuex store. */
export function useAppStore() {
  const store = useStore<AppState>();
  return {
    activeHubTab: computed(() => store.state.activeHubTab),
    sidebarCollapsed: computed(() => store.state.sidebarCollapsed),
    selectHubTab: (tabId: string) => store.dispatch(ActionType.SelectHubTab, tabId),
    toggleSidebar: () => store.dispatch(ActionType.ToggleSidebar),
  };
}
