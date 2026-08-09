import type { MutationTree } from "vuex";
import type { AppState } from "../state/appState";

export enum MutationType {
  SetActiveHubTab = "SET_ACTIVE_HUB_TAB",
  SetSidebarCollapsed = "SET_SIDEBAR_COLLAPSED",
}

export const mutations: MutationTree<AppState> = {
  [MutationType.SetActiveHubTab](state, tabId: string) {
    state.activeHubTab = tabId;
  },
  [MutationType.SetSidebarCollapsed](state, collapsed: boolean) {
    state.sidebarCollapsed = collapsed;
  },
};
